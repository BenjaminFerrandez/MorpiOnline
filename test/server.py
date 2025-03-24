import socket
import threading
import json
import time
import random
import uuid


class TicTacToeGame:
    def __init__(self, player1, player2):
        self.board = [" " for _ in range(9)]
        self.current_player = "X"
        self.players = {"X": player1, "O": player2}
        self.game_id = str(uuid.uuid4())
        self.winner = None
        self.is_draw = False
        self.game_over = False
        self.rematch_requests = set()  # Pour suivre les demandes de revanche

    def make_move(self, position):
        """Effectue un mouvement sur le plateau"""
        if 0 <= position <= 8 and self.board[position] == " " and not self.game_over:
            self.board[position] = self.current_player

            # Vérification de la victoire
            if self.check_winner():
                self.winner = self.current_player
                self.game_over = True
                return True

            # Vérification du match nul
            if " " not in self.board:
                self.is_draw = True
                self.game_over = True
                return True

            # Changement de joueur
            self.current_player = "O" if self.current_player == "X" else "X"
            return True
        return False

    def check_winner(self):
        """Vérifie s'il y a un gagnant"""
        # Lignes horizontales
        for i in range(0, 9, 3):
            if self.board[i] != " " and self.board[i] == self.board[i + 1] == self.board[i + 2]:
                return True

        # Lignes verticales
        for i in range(3):
            if self.board[i] != " " and self.board[i] == self.board[i + 3] == self.board[i + 6]:
                return True

        # Diagonales
        if self.board[0] != " " and self.board[0] == self.board[4] == self.board[8]:
            return True
        if self.board[2] != " " and self.board[2] == self.board[4] == self.board[6]:
            return True

        return False

    def reset_game(self):
        """Réinitialise le jeu pour une revanche"""
        self.board = [" " for _ in range(9)]
        # Inverse les rôles pour la revanche
        self.players = {"X": self.players["O"], "O": self.players["X"]}
        self.current_player = "X"
        self.winner = None
        self.is_draw = False
        self.game_over = False
        self.rematch_requests.clear()

    def request_rematch(self, client_id):
        """Enregistre une demande de revanche"""
        self.rematch_requests.add(client_id)
        return len(self.rematch_requests) == 2  # True si les deux joueurs ont demandé une revanche

    def get_state(self):
        """Renvoie l'état actuel du jeu"""
        return {
            "board": self.board,
            "current_player": self.current_player,
            "game_over": self.game_over,
            "winner": self.winner,
            "is_draw": self.is_draw,
            "game_id": self.game_id,
            "rematch_requests": list(self.rematch_requests)
        }


class TicTacToeServer:
    def __init__(self, host="0.0.0.0", port=5555):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = {}  # Stocke les connexions client {client_id: (conn, addr)}
        self.waiting_players = []  # Joueurs en attente d'une partie
        self.games = {}  # Parties en cours {game_id: TicTacToeGame}
        self.client_to_game = {}  # Map client_id -> game_id

    def start(self):
        """Démarre le serveur"""
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)
        print(f"Serveur démarré sur {self.host}:{self.port}")

        try:
            while True:
                conn, addr = self.server_socket.accept()
                client_id = str(uuid.uuid4())
                self.clients[client_id] = (conn, addr)
                print(f"Nouvelle connexion de {addr}, client_id: {client_id}")

                # Démarre un thread pour gérer ce client
                client_thread = threading.Thread(target=self.handle_client, args=(client_id,))
                client_thread.daemon = True
                client_thread.start()

        except KeyboardInterrupt:
            print("Arrêt du serveur...")
        finally:
            self.server_socket.close()

    def handle_client(self, client_id):
        """Gère la connexion d'un client spécifique"""
        conn, addr = self.clients[client_id]

        try:
            # Envoie l'ID client
            self.send_message(client_id, {"type": "connection", "client_id": client_id})

            # Ajoute le joueur à la file d'attente
            self.waiting_players.append(client_id)
            self.check_matchmaking()

            while True:
                # Réception des données du client
                data = conn.recv(1024).decode('utf-8')
                if not data:
                    break

                try:
                    message = json.loads(data)
                    self.process_message(client_id, message)
                except json.JSONDecodeError:
                    print(f"Données JSON invalides: {data}")

        except (ConnectionResetError, BrokenPipeError):
            print(f"Connexion perdue avec le client {client_id}")
        finally:
            # Nettoyage quand un client se déconnecte
            self.cleanup_client(client_id)

    def cleanup_client(self, client_id):
        """Nettoie les ressources lorsqu'un client se déconnecte"""
        if client_id in self.waiting_players:
            self.waiting_players.remove(client_id)

        if client_id in self.client_to_game:
            game_id = self.client_to_game[client_id]
            game = self.games.get(game_id)
            if game:
                # Trouver l'autre joueur
                other_player_id = None
                for symbol, pid in game.players.items():
                    if pid != client_id:
                        other_player_id = pid
                        break

                if other_player_id:
                    # Informer l'autre joueur de la déconnexion et terminer la partie
                    self.send_message(other_player_id, {"type": "opponent_disconnected"})

                    # Retirer l'autre joueur de la partie et le remettre en file d'attente
                    if other_player_id in self.client_to_game:
                        del self.client_to_game[other_player_id]

                    # Remettre l'autre joueur en file d'attente s'il est toujours connecté
                    if other_player_id in self.clients:
                        self.waiting_players.append(other_player_id)
                        self.check_matchmaking()

                # Supprimer la partie
                del self.games[game_id]

            # Supprimer le mapping client->partie
            del self.client_to_game[client_id]

        # Fermer et supprimer la connexion
        if client_id in self.clients:
            conn, _ = self.clients[client_id]
            conn.close()
            del self.clients[client_id]

    def check_matchmaking(self):
        """Vérifie s'il y a des joueurs en attente pour créer une nouvelle partie"""
        if len(self.waiting_players) >= 2:
            # Prend les deux premiers joueurs en attente
            player1 = self.waiting_players.pop(0)
            player2 = self.waiting_players.pop(0)

            # Vérifie que les joueurs sont toujours connectés
            if player1 not in self.clients or player2 not in self.clients:
                # Remettre en file d'attente le joueur encore connecté
                if player1 in self.clients:
                    self.waiting_players.append(player1)
                if player2 in self.clients:
                    self.waiting_players.append(player2)
                return

            # Crée une nouvelle partie
            game = TicTacToeGame(player1, player2)
            self.games[game.game_id] = game

            # Associe les clients à la partie
            self.client_to_game[player1] = game.game_id
            self.client_to_game[player2] = game.game_id

            # Informe les joueurs du début de la partie
            self.send_message(player1, {
                "type": "game_start",
                "player_symbol": "X",
                "game_id": game.game_id,
                "opponent_id": player2
            })

            self.send_message(player2, {
                "type": "game_start",
                "player_symbol": "O",
                "game_id": game.game_id,
                "opponent_id": player1
            })

            # Envoie l'état initial du jeu
            self.broadcast_game_state(game.game_id)

            print(f"Nouvelle partie créée: {game.game_id} entre {player1} et {player2}")

    def process_message(self, client_id, message):
        """Traite un message reçu d'un client"""
        message_type = message.get("type")

        if message_type == "move":
            # Le client fait un mouvement
            game_id = self.client_to_game.get(client_id)
            if not game_id:
                return

            game = self.games.get(game_id)
            if not game:
                return

            # Vérifie si c'est le tour du joueur
            player_symbol = next((symbol for symbol, pid in game.players.items() if pid == client_id), None)
            if player_symbol != game.current_player:
                self.send_message(client_id, {"type": "error", "message": "Ce n'est pas votre tour"})
                return

            # Effectue le mouvement
            position = message.get("position")
            if position is not None and game.make_move(position):
                # Diffuse le nouvel état du jeu aux deux joueurs
                self.broadcast_game_state(game_id)

        elif message_type == "rematch_request":
            # Demande de revanche
            game_id = self.client_to_game.get(client_id)
            if not game_id:
                return

            game = self.games.get(game_id)
            if not game or not game.game_over:
                return

            # Enregistre la demande de revanche
            if game.request_rematch(client_id):
                # Les deux joueurs ont demandé une revanche, réinitialiser le jeu
                game.reset_game()

                # Informer les joueurs de la revanche
                for symbol, player_id in game.players.items():
                    self.send_message(player_id, {
                        "type": "rematch_accepted",
                        "player_symbol": symbol
                    })

                # Envoie l'état initial du nouveau jeu
                self.broadcast_game_state(game_id)
            else:
                # Informer les deux joueurs qu'une demande de revanche a été faite
                self.broadcast_game_state(game_id)

    def broadcast_game_state(self, game_id):
        """Envoie l'état actuel du jeu aux deux joueurs"""
        game = self.games.get(game_id)
        if not game:
            return

        game_state = game.get_state()
        for symbol, player_id in game.players.items():
            if player_id in self.clients:  # Vérifie que le joueur est toujours connecté
                self.send_message(player_id, {
                    "type": "game_state",
                    "state": game_state,
                    "your_symbol": symbol
                })

    def send_message(self, client_id, message):
        """Envoie un message à un client spécifique"""
        if client_id not in self.clients:
            return

        conn, _ = self.clients[client_id]
        try:
            conn.sendall((json.dumps(message) + "\n").encode('utf-8'))
        except (ConnectionResetError, BrokenPipeError):
            print(f"Erreur d'envoi au client {client_id}")
            self.cleanup_client(client_id)


if __name__ == "__main__":
    server = TicTacToeServer()
    server.start()