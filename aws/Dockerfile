# AWS Lambda 컨테이너 이미지
FROM public.ecr.aws/lambda/python:3.11

ENV PYTHONIOENCODING=utf-8
ENV PYTHONUTF8=1

COPY requirements.txt ./
RUN pip install -r requirements.txt mangum --no-cache-dir

COPY api/ ./api/
COPY config/ ./config/
COPY src/ ./src/
COPY static/ ./static/
COPY public/ ./public/
COPY data/ ./data/

CMD ["api.lambda_handler.handler"]
