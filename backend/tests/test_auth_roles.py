import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app import auth, dataset_manager as dm

class RolesTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=auth.ROOT
        auth.ROOT=Path(self.temp.name)/'auth'
        self.client=TestClient(app)
    def tearDown(self):
        auth.ROOT=self.old
        self.temp.cleanup()
    def login(self,role='user'):
        return self.client.post('/api/auth/login',json={'username':role,'password':'User@2026' if role=='user' else 'Admin@2026','role':role})
    def test_login_role_cannot_grant_admin(self):
        self.assertEqual(self.client.get('/api/data/batches').status_code,401)
        self.assertEqual(self.client.post('/api/auth/login',json={'username':'user','password':'User@2026','role':'admin'}).status_code,401)
        self.assertEqual(self.login().status_code,200)
        self.assertEqual(self.client.get('/api/auth/me').json()['data']['role'],'user')
        self.assertEqual(self.client.get('/api/admin/users').status_code,403)
        self.assertEqual(self.client.post('/api/data/batches/fake/activate').status_code,403)
        self.assertEqual(self.client.post('/api/auth/logout').status_code,200)
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)
    def test_accounts_and_last_admin(self):
        self.login('admin')
        self.assertEqual(self.client.post('/api/admin/users/update',json={'username':'admin','role':'user','enabled':True}).status_code,400)
        self.assertEqual(self.client.post('/api/admin/users',json={'username':'tester','password':'Testing@2026','role':'user'}).status_code,200)
        self.client.post('/api/auth/logout')
        self.assertEqual(self.client.post('/api/auth/login',json={'username':'tester','password':'Testing@2026','role':'user'}).status_code,200)
        with auth.db() as con: con.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)
    def test_ownership_and_review(self):
        self.login()
        value={'id':'a'*32,'owner':'other','status':'uploading','metadataConfirmed':True}
        with patch.object(dm,'job',return_value=value):
            self.assertEqual(self.client.get('/api/data/imports/'+value['id']).status_code,403)
        value['owner']='user'
        with patch.object(dm,'job',return_value=value),patch.object(dm,'preview',return_value={'complete':True,'errors':[]}),patch.object(dm,'_save') as save:
            r=self.client.post('/api/data/imports/'+value['id']+'/finalize')
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()['data']['reviewStatus'],'pending')
            save.assert_called_once()
            self.assertEqual(self.client.post('/api/data/imports/'+value['id']+'/metadata',json={}).status_code,403)
        self.login('admin')
        with patch.object(dm,'job',return_value=value),patch.object(dm,'_save'):
            r=self.client.post('/api/admin/imports/'+value['id']+'/reject',json={'reason':'补充来源'})
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()['data']['reviewStatus'],'returned')
    def test_disabled_session_and_origin(self):
        self.login()
        with auth.db() as con:con.execute("UPDATE users SET enabled=0 WHERE username='user'")
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)
        self.assertEqual(self.client.post('/api/auth/login',headers={'origin':'https://example.org'},json={'username':'admin','password':'Admin@2026','role':'admin'}).status_code,403)

if __name__=='__main__':unittest.main()
