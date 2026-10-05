import errno
import http.client
import io
import json
import socket
import ssl
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch, Mock
from brand_discovery.collector import public_ip, Refused
from brand_discovery.instagram import PublicFetcher, classify_error

URL='https://www.instagram.com/synthetic_test_01/'

class NetworkDiagnosticTests(unittest.TestCase):
    def addresses(self):
        return [(socket.AF_INET6,socket.SOCK_STREAM,0,'',('2606:4700:4700::1111',443,0,0)),
                (socket.AF_INET,socket.SOCK_STREAM,0,'',('8.8.8.8',443))]
    def test_dual_stack_selects_ipv4_without_additional_attempt(self):
        # The previous lexicographic selector chose IPv6 ('2' sorts before '8').
        self.assertEqual(sorted(['2606:4700:4700::1111','8.8.8.8'])[0],'2606:4700:4700::1111')
        with patch('socket.getaddrinfo',return_value=self.addresses()):
            self.assertEqual(public_ip('synthetic.invalid'),'8.8.8.8')
    def test_all_addresses_still_must_be_public(self):
        addresses=self.addresses()+[(socket.AF_INET,socket.SOCK_STREAM,0,'',('127.0.0.1',443))]
        with patch('socket.getaddrinfo',return_value=addresses):
            with self.assertRaises(Refused):public_ip('synthetic.invalid')
    def test_ipv6_only_not_rewritten_or_retried(self):
        with patch('socket.getaddrinfo',return_value=self.addresses()[:1]):
            self.assertEqual(public_ip('synthetic.invalid'),'2606:4700:4700::1111')
    def test_non_sensitive_classification(self):
        examples=[(socket.gaierror(-2,'PRIVATE_URL_SENTINEL'),'dns_error'),
                  (ssl.SSLError('PRIVATE_URL_SENTINEL'),'tls_error'),
                  (TimeoutError('PRIVATE_URL_SENTINEL'),'timeout'),
                  (ConnectionRefusedError('PRIVATE_URL_SENTINEL'),'connection_refused'),
                  (ConnectionResetError('PRIVATE_URL_SENTINEL'),'connection_reset'),
                  (OSError(errno.ENETUNREACH,'PRIVATE_URL_SENTINEL'),'network_unreachable'),
                  (OSError(errno.EAFNOSUPPORT,'PRIVATE_URL_SENTINEL'),'address_family_unavailable'),
                  (http.client.BadStatusLine('PRIVATE_URL_SENTINEL'),'http_protocol_error'),
                  (ValueError('PRIVATE_URL_SENTINEL'),'unclassified_internal_error')]
        for exc,expected in examples:self.assertEqual(classify_error(exc),expected)
    def test_request_failure_is_quiet_and_attempted_only_once(self):
        conn=Mock();conn.request.side_effect=OSError(errno.ENETUNREACH,'PRIVATE_URL_SENTINEL')
        output=io.StringIO()
        with patch('brand_discovery.instagram.PinnedTLS',return_value=conn),redirect_stdout(output),redirect_stderr(output):
            result=PublicFetcher().get(URL)
        self.assertEqual(result,{'status':'network_error','error_category':'network_unreachable'})
        self.assertEqual(conn.request.call_count,1)
        conn.close.assert_called_once()
        self.assertNotIn('PRIVATE_URL_SENTINEL',json.dumps(result))
        self.assertEqual(output.getvalue(),'')

if __name__=='__main__':unittest.main()
