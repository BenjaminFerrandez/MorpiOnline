import socket
import threading
import json
import time
from datetime import datetime
from database import Database

class Player:
    def __init__(self, username, client_socket, address):
        self.username = username
        self.client_socket = client_socket
        self.address = address
        self.join_time = datetime.now()
        self.id = None
        self.in_game = False

class Game:
    def __init__(self, player1, player2, game_id):
        self.player1 = player1
        self.player2 = player2
        self.game_id = game_id
        self.board = [" " for _ in range(9)]
        self.current_turn = player1
        self.turns_count = 0
        self.winner = None
        self.finished = False

    def make_move(self, player, position):
        if self.current_turn != player or self.finished:
            return False

        if position < 0 or position > 8 or self.board[position] != " ":
            return False

        symbol = "X" if player == self.player1 else "O"
        self.board[position] = symbol
        self.turns_count += 1

        winner_symbol = self.check_winner()
        if winner_symbol:
            self.winner = self.player1 if winner_symbol == "X" else self.player2
            self.finished = True
        elif self.turns_count == 9:
            self.finished = True

        self.current_turn = self.player2 if player == self.player1 else self.player1
        return True

    def check_winner(self):
        # Vérifier les lignes
        for i in range(0, 9, 3):
            if self.board[i] != " " and self.board[i] == self.board[i+1] == self.board[i+2]:
                return self.board[i]

        for i in range(3):
            if self.board[i] != " " and self.board[i] == self.board[i+3] == self.board[i+6]:
                return self.board[i]

        if self.board[0] != " " and self.board[0] == self.board[4] == self.board[8]:
            return self.board[0]
        if self.board[2] != " " and self.board[2] == self.board[4] == self.board[6]:
            return self.board[2]

        return None

    def get_state(self):
        return {
            "board": self.board,
            "current_turn": self.current_turn.username,
            "turns_count": self.turns_count,
            "finished": self.finished,
            "winner": self.winner.username if self.winner else None
        }

class Server:
    def __init__(self, host="localhost", port=5555):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)

        self.queue = []
        self.active_games = {}
        self.players = {}

        self.db = Database()

        self.queue_check_thread = threading.Thread(target=self.check_queue)
        self.queue_check_thread.daemon = True
        self.queue_check_thread.start()

        print(f"Server started on {self.host}:{self.port}")

    def start(self):
        try:
            while True:
                client_socket, address = self.server_socket.accept()
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, address))
                client_thread.daemon = True
                client_thread.start()
        except KeyboardInterrupt:
            print("Server shutting down...")
            self.db.close()
            self.server_socket.close()

    def handle_client(self, client_socket, address):
        try:
            # Recevoir le nom d'utilisateur
            data = client_socket.recv(1024).decode('utf-8')
            try:
                message = json.loads(data)
                if message["action"] == "login":
                    username = message["username"]

                    # Vérifier si le joueur existe déjà dans la base de données
                    player_data = self.db.get_player_by_username(username)
                    if player_data:
                        player_id = player_data[0]
                    else:
                        player_id = self.db.add_player(username)

                    # Créer un objet Player
                    player = Player(username, client_socket, address)
                    player.id = player_id
                    self.players[client_socket] = player

                    # Envoyer une confirmation
                    response = {
                        "action": "login_success",
                        "player_id": player_id
                    }
                    client_socket.send(json.dumps(response).encode('utf-8'))

                    # Attendre d'autres commandes du client
                    self.handle_player_commands(player)
            except json.JSONDecodeError:
                client_socket.send(json.dumps({"error": "Invalid JSON format"}).encode('utf-8'))
        except Exception as e:
            print(f"Error handling client {address}: {str(e)}")
        finally:
            if client_socket in self.players:
                player = self.players[client_socket]
                if player in self.queue:
                    self.queue.remove(player)
                del self.players[client_socket]
            client_socket.close()

    def handle_player_commands(self, player):
        while True:
            try:
                data = player.client_socket.recv(1024).decode('utf-8')
                if not data:
                    break

                message = json.loads(data)
                action = message.get("action")

                if action == "join_queue":
                    if player in self.queue:
                        response = {"action": "error", "message": "Already in queue"}
                    elif player.in_game:
                        response = {"action": "error", "message": "Already in game"}
                    else:
                        self.queue.append(player)
                        response = {
                            "action": "joined_queue",
                            "position": len(self.queue),
                            "queue_length": len(self.queue),
                            "join_time": player.join_time.strftime("%H:%M:%S")
                        }
                        self.broadcast_queue_update()

                    player.client_socket.send(json.dumps(response).encode('utf-8'))

                elif action == "leave_queue":
                    if player in self.queue:
                        self.queue.remove(player)
                        response = {"action": "left_queue"}
                        self.broadcast_queue_update()
                    else:
                        response = {"action": "error", "message": "Not in queue"}

                    player.client_socket.send(json.dumps(response).encode('utf-8'))

                elif action == "make_move":
                    game = None
                    for game_id, g in self.active_games.items():
                        if g.player1 == player or g.player2 == player:
                            game = g
                            break

                    if not game:
                        response = {"action": "error", "message": "Not in game"}
                    else:
                        position = message.get("position")
                        if position is None:
                            response = {"action": "error", "message": "No position provided"}
                        else:
                            success = game.make_move(player, position)
                            if success:
                                game_state = game.get_state()
                                game_update = {
                                    "action": "game_update",
                                    "game_state": game_state
                                }
                                game.player1.client_socket.send(json.dumps(game_update).encode('utf-8'))
                                game.player2.client_socket.send(json.dumps(game_update).encode('utf-8'))

                                if game.finished:
                                    winner_id = game.winner.id if game.winner else None
                                    self.db.update_game_winner(game.game_id, winner_id, game.turns_count)

                                    end_game = {
                                        "action": "game_over",
                                        "winner": game.winner.username if game.winner else None,
                                        "message": f"{game.winner.username} a gagné!" if game.winner else "Match nul!"
                                    }
                                    game.player1.client_socket.send(json.dumps(end_game).encode('utf-8'))
                                    game.player2.client_socket.send(json.dumps(end_game).encode('utf-8'))

                                    game.player1.in_game = False
                                    game.player2.in_game = False

                                    del self.active_games[game.game_id]

                                response = {"action": "move_success"}
                            else:
                                response = {"action": "error", "message": "Invalid move"}

                    player.client_socket.send(json.dumps(response).encode('utf-8'))

                elif action == "chat_message":
                    game = None
                    for game_id, g in self.active_games.items():
                        if g.player1 == player or g.player2 == player:
                            game = g
                            break

                    if not game:
                        response = {"action": "error", "message": "Not in game"}
                        player.client_socket.send(json.dumps(response).encode('utf-8'))
                    else:
                        message_content = message.get("message")
                        if not message_content:
                            response = {"action": "error", "message": "No message content"}
                            player.client_socket.send(json.dumps(response).encode('utf-8'))
                        else:
                            chat_message = {
                                "action": "chat_message",
                                "from": player.username,
                                "message": message_content,
                                "time": datetime.now().strftime("%H:%M:%S")
                            }

                            opponent = game.player2 if player == game.player1 else game.player1
                            opponent.client_socket.send(json.dumps(chat_message).encode('utf-8'))

                            response = {"action": "message_sent"}
                            player.client_socket.send(json.dumps(response).encode('utf-8'))

                elif action == "get_stats":
                    stats = self.db.get_player_stats(player.id)
                    if stats:
                        total_games, wins = stats
                        total_games = int(total_games) if total_games is not None else 0
                        wins = int(wins) if wins is not None else 0
                        losses = total_games - wins

                        response = {
                            "action": "stats",
                            "total_games": total_games,
                            "wins": wins,
                            "losses": losses
                        }
                    else:
                        response = {
                            "action": "stats",
                            "total_games": 0,
                            "wins": 0,
                            "losses": 0
                        }

                    player.client_socket.send(json.dumps(response).encode('utf-8'))

            except json.JSONDecodeError:
                player.client_socket.send(json.dumps({"error": "Invalid JSON format"}).encode('utf-8'))
            except Exception as e:
                print(f"Error handling command from {player.username}: {str(e)}")
                break

    def check_queue(self):
        while True:
            try:
                if len(self.queue) >= 2:
                    player1 = self.queue.pop(0)
                    player2 = self.queue.pop(0)

                    player1.in_game = True
                    player2.in_game = True

                    game_id = self.db.create_game(player1.id, player2.id)

                    game = Game(player1, player2, game_id)
                    self.active_games[game_id] = game

                    game_start = {
                        "action": "game_start",
                        "opponent": player2.username,
                        "symbol": "X",
                        "your_turn": True
                    }
                    player1.client_socket.send(json.dumps(game_start).encode('utf-8'))

                    game_start = {
                        "action": "game_start",
                        "opponent": player1.username,
                        "symbol": "O",
                        "your_turn": False
                    }
                    player2.client_socket.send(json.dumps(game_start).encode('utf-8'))

                    self.broadcast_queue_update()

                time.sleep(1)
            except Exception as e:
                print(f"Error in queue check: {str(e)}")

    def broadcast_queue_update(self):
        queue_update = {
            "action": "queue_update",
            "queue_length": len(self.queue),
            "players": [{"username": p.username, "join_time": p.join_time.strftime("%H:%M:%S")} for p in self.queue]
        }

        for player in self.queue:
            try:
                player.client_socket.send(json.dumps(queue_update).encode('utf-8'))
            except:
                pass

if __name__ == "__main__":
    server = Server()
    server.start()