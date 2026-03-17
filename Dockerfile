FROM python:3.11-alpine

COPY ad_radio_playlist.py requirements.txt /

RUN pip3 install --no-cache-dir -r requirements.txt

CMD ["python3", "ad_radio_playlist.py"]
