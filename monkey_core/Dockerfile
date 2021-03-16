FROM ubuntu:18.04

RUN apt-get update && \
    apt-get install -y python3 python3-pip python3-dev lsb-release curl && \
    apt-get clean

RUN pip3 install --upgrade pip setuptools && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    ln -s /usr/bin/pip3 /usr/bin/pip


RUN useradd -ms /bin/bash monkey

ADD requirements.txt /home/monkey/requirements.txt
RUN pip3 install -r /home/monkey/requirements.txt

# Install gcsfuse
RUN export GCSFUSE_REPO=gcsfuse-`lsb_release -c -s` && \ 
    echo "deb http://packages.cloud.google.com/apt $GCSFUSE_REPO main" | tee /etc/apt/sources.list.d/gcsfuse.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -

RUN apt-get update && \ 
    apt-get install -y gcsfuse vim

RUN mkdir /monkeyfs && \ 
    chown monkey /monkeyfs

ENV MONKEYFS_PATH=/monkeyfs

USER monkey
WORKDIR /home/monkey

COPY --chown=monkey . /home/monkey/

CMD [ "/bin/bash" ]
# ENTRYPOINT [ "./home/monkey/entrypoint.sh" ]