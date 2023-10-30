FROM python:3.11-alpine

COPY update_playlist.py requirements.txt /

RUN pip3 install -r requirements.txt

# RUN set -ex

EXPOSE 8099

# CMD ["python", "./update_playlist.py"]
CMD ["uvicorn", "update_playlist:app", "--host", "0.0.0.0", "--port", "8099"]
