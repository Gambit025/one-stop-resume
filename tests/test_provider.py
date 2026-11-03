import io
import json
import os
import unittest
from unittest.mock import patch
import urllib.error
from llm_generator import structure_resume_via_llm


class Provider(unittest.TestCase):
    def test_json_and_request_contract(self):
        content={'name':'测试','contact':'','sections':[]}
        response={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(content)}}]}
        with patch.dict(os.environ,{'GROQ_API_KEY':'fake-test-only'}), patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as call:
            self.assertEqual(structure_resume_via_llm('测试'),content)
            req=call.call_args.args[0]
            payload=json.loads(req.data)
            self.assertEqual(payload['response_format']['type'],'json_schema')
            self.assertTrue(payload['response_format']['json_schema']['strict'])
            self.assertEqual(payload['reasoning_effort'],'low')
            self.assertEqual(req.get_header('User-agent'),'OneStopResume/1.0')
    def test_quota_auth_network_and_truncation(self):
        cases=[(urllib.error.HTTPError('test',429,'quota',{},None),'免费额度'),
               (urllib.error.HTTPError('test',401,'auth',{},None),'密钥'),
               (urllib.error.URLError('test'),'连接')]
        for error,message in cases:
            with self.subTest(message=message),patch.dict(os.environ,{'GROQ_API_KEY':'fake-test-only'}),patch('urllib.request.urlopen',side_effect=error):
                with self.assertRaisesRegex(RuntimeError,message): structure_resume_via_llm('synthetic')
        response={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}
        with patch.dict(os.environ,{'GROQ_API_KEY':'fake-test-only'}),patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(response).encode())):
            with self.assertRaisesRegex(RuntimeError,'截断'): structure_resume_via_llm('synthetic')

if __name__=='__main__':unittest.main()
