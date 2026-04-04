# -*- coding: utf-8 -*-
"""
AWS Lambda 어댑터 — 통합 앱을 Lambda로 서빙

Mangum이 FastAPI ASGI → Lambda 이벤트 변환을 처리.
API Gateway (REST/HTTP) 또는 ALB와 연동 가능.

배포:
  sam build && sam deploy --guided
  또는 Docker Lambda: aws/Dockerfile 사용
"""

from api.app import app

try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    # mangum 미설치 시 기본 핸들러
    def handler(event, context):
        return {
            "statusCode": 200,
            "body": '{"error": "mangum 패키지를 설치하세요: pip install mangum"}',
            "headers": {"Content-Type": "application/json"},
        }
