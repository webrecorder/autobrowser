FROM python:3.7.1

COPY requirements.txt /temp/requirements.txt
RUN cd /temp && pip install -r requirements.txt


COPY chrome-remote-interface-py /tmp/chrome-remote-interface-py
COPY simplechrome /tmp/simplechrome

RUN cd /tmp/chrome-remote-interface-py && python setup.py install
RUN cd /tmp/simplechrome && python setup.py install


WORKDIR /tmp

