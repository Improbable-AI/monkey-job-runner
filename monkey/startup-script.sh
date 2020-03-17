#!/bin/bash

apt-get update

cd $HOME
echo "Hello there" > test.txt
echo "asdf $USER" > user.txt

echo $GCP_USER > "gcpuser.txt"

apt-get -y update
apt-get -y --no-install-recommends install \
    curl \
    apt-utils \
    apt-transport-https \
    ca-certificates \
    curl \
    software-properties-common



echo Adding Graphis Drivers PPA
add-apt-repository -y ppa:graphics-drivers/ppa
echo Adding Docker PPA
add-apt-repository -y "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -

apt-get update
apt-get install -y \
  nvidia-384 \
  nvidia-modprobe \
  docker-ce

echo Nvidia Docker PPA
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | \
  sudo apt-key add -
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list
apt-get update

# Install nvidia-docker2 and reload the Docker daemon configuration
apt-get install -y nvidia-docker2


groupadd docker
usermod -aG docker $GCP_US


echo "Done" > "done.txt"

# sudo reboot