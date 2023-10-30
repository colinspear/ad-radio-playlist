FROM python:3.11-alpine

COPY ad_radio_playlist.py requirements.txt /

RUN pip3 install -r requirements.txt

EXPOSE 8099

CMD ["uvicorn", "ad_radio_playlist:app", "--host", "0.0.0.0", "--port", "8099"]
