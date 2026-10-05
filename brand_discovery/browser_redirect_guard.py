"""Stop redirect responses before Chromium can follow them. No response body read."""
from .instagram import classify_redirect

def install_response_guard(context,page,policy):
    session=context.new_cdp_session(page)
    frame=session.send('Page.getFrameTree')['frameTree']['frame']['id']
    def paused(event):
        request_id=event['requestId']
        main=event.get('resourceType')=='Document' and event.get('frameId')==frame
        code=event.get('responseStatusCode')
        try:
            if code is None:
                if main:policy.block('network_error','navigation_response_error')
                session.send('Fetch.failRequest',{'requestId':request_id,'errorReason':'BlockedByClient'});return
            if main:policy.navigation_response(code)
            if code in (301,302,303,307,308):
                if main:
                    location=next((h['value'] for h in event.get('responseHeaders',[]) if h['name'].lower()=='location'),'')
                    decision=classify_redirect(event['request']['url'],location,code)
                    policy.block(decision['status'],decision['restriction_evidence'])
                else:policy.blocked_resources+=1
                session.send('Fetch.failRequest',{'requestId':request_id,'errorReason':'BlockedByClient'});return
            if code in (401,403,429,451) or policy.stop:
                if not policy.stop:policy.block('http_'+str(code),'response_access_restriction')
                session.send('Fetch.failRequest',{'requestId':request_id,'errorReason':'BlockedByClient'});return
            session.send('Fetch.continueResponse',{'requestId':request_id})
        except Exception:
            policy.block('response_guard_error','response_not_safely_released')
            try:session.send('Fetch.failRequest',{'requestId':request_id,'errorReason':'BlockedByClient'})
            except Exception:pass
    session.on('Fetch.requestPaused',paused)
    session.send('Fetch.enable',{'patterns':[{'urlPattern':'*','requestStage':'Response'}]})
    return session
