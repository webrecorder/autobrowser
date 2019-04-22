FROM python:3.7.3

COPY ./requirements.txt /temp/requirements.txt
RUN cd /temp && pip install -r requirements.txt

WORKDIR /app

ADD . /app

CMD python -u /app/driver.py


