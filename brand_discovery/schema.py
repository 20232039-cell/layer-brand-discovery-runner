"""Lossless input adapter; source decisions never become collector verdicts."""
MASTER_FIELDS = ['LAYER 선별', '브랜드(한글)', '브랜드(영문)', '선별 이유', '공식몰 링크', '플랫폼', '성별', '주력 품목', '찾은 곳', '확인 메모', '인스타그램 링크', '공식 이메일', '가격대 근거', '품질 관련 공개정보', '인스타그램 팔로워 수', '팔로워 수 확인일', '팔로워 수 근거']

def first(row, keys):
    return next((str(row[k]) for k in keys if row.get(k)), '')

def adapt(row):
    return {
        'name': first(row, ('브랜드(영문)', '브랜드(한글)', 'name', 'name_en', 'brand')),
        'official_url': first(row, ('공식몰 링크', '공식몰', 'official_url', 'site_url')),
        'discovery_source': first(row, ('찾은 곳', '발견 경로', 'source')),
        'source_verdict': first(row, ('판정', 'LAYER 선별', 'decision')),
        'source_record': dict(row),
        'source_schema': 'master_17' if all(k in row for k in MASTER_FIELDS) else ('reconciliation_queue' if 'verification_excel_row' in row else 'candidate'),
    }
