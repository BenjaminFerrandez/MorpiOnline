# MorpiOnline
Projet fil rouge d'Ynov Montpellier Campus.\
Benjamin FERRANDEZ \
Thomas Nebra
## Installation
1. Clone le repo sur un poste de travaille (avoir au préalable python 3.13+) .
2. Importez la base de données morpionline.sql dans une base de données mysql.
3. Installez les dépendances avec la commande suivante :
```bash
pip install tkinter
pip install mysql-connector-python
```
4. Lancez le serveur avec la commande suivante :
```bash
python3 server.py
```
5. Lancez le client avec la commande suivante :
```bash
python3 client.py
```
## Fonctionnalités
- Connexion à un serveur avec un pseudo
- Rejoindre une file d'attente
- Jouer à une partie avec un autre joueur
- Communiquer avec l'autre joueur