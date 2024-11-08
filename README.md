# Connections

Create a .env inside the root directory with variables

GeminiAPI_KEY=""
Mistral_key=""
CoreAPI_KEY=""

Install docker

curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

Clone the repository code

git clone https://github.com/ryanjzheng/Connections
cd Connections

Build image and deploy container

sudo docker compose up --build