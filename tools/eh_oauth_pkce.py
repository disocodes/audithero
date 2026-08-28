#!/usr/bin/env python3
import argparse,base64,hashlib,secrets,urllib.parse,requests
AUTH='https://oauth.employmenthero.com/oauth2/authorize';TOKEN='https://oauth.employmenthero.com/oauth2/token'
def verifier():return secrets.token_urlsafe(64)[:96]
def challenge(v):return base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).decode().rstrip('=')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--client-id',required=True);ap.add_argument('--client-secret',required=True);ap.add_argument('--redirect-uri',required=True);ap.add_argument('--code');ap.add_argument('--verifier');a=ap.parse_args()
    if not a.code:
        v=verifier();q=urllib.parse.urlencode({'client_id':a.client_id,'redirect_uri':a.redirect_uri,'response_type':'code','code_challenge':challenge(v),'code_challenge_method':'S256'});print(f'{AUTH}?{q}');print('\nSAVE VERIFIER:\n'+v);return
    if not a.verifier:raise SystemExit('--verifier required')
    r=requests.post(TOKEN,data={'grant_type':'authorization_code','redirect_uri':a.redirect_uri,'client_id':a.client_id,'client_secret':a.client_secret,'code':a.code,'code_verifier':a.verifier},headers={'Content-Type':'application/x-www-form-urlencoded'},timeout=60);r.raise_for_status();print(r.json()['refresh_token'])
if __name__=='__main__':main()
