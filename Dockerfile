
# build behaviors
FROM node:10 as behaviors

WORKDIR /build

RUN git clone -b make-pausable https://github.com/webrecorder/wr-behaviors

WORKDIR /build/wr-behaviors

RUN yarn install && yarn run build-dev



FROM python:3.7.1 as driver

COPY requirements.txt /temp/requirements.txt
RUN cd /temp && pip install -r requirements.txt

WORKDIR /app

ADD . /app

COPY --from=behaviors /build/wr-behaviors/dist /app/autobrowser/behaviors/behaviorjs

CMD python -u /app/driver.py


