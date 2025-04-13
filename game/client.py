import socket
import json
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
from datetime import datetime

class TicTacToeClient:
    def __init__(self, host="localhost", port=5555):
        self.host = host
        self.port = port
        self.client_socket = None
        self.username = None
        self.player_id = None
        self.in_queue = False
        self.in_game = False
        self.symbol = None
        self.my_turn = False
        self.opponent = None
        self.board = [" " for _ in range(9)]

        # Interface principale
        self.root = tk.Tk()
        self.root.title("Tic Tac Toe - Client")
        self.root.geometry("800x600")
        self.root.resizable(False, False)

        # Frame de connexion
        self.login_frame = tk.Frame(self.root)
        self.login_frame.pack(pady=50)

        tk.Label(self.login_frame, text="Nom d'utilisateur:").grid(row=0, column=0, padx=5, pady=5)
        self.username_entry = tk.Entry(self.login_frame, width=20)
        self.username_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(self.login_frame, text="Serveur:").grid(row=1, column=0, padx=5, pady=5)
        self.server_entry = tk.Entry(self.login_frame, width=20)
        self.server_entry.insert(0, host)
        self.server_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(self.login_frame, text="Port:").grid(row=2, column=0, padx=5, pady=5)
        self.port_entry = tk.Entry(self.login_frame, width=20)
        self.port_entry.insert(0, str(port))
        self.port_entry.grid(row=2, column=1, padx=5, pady=5)

        self.connect_button = tk.Button(self.login_frame, text="Se connecter", command=self.connect)
        self.connect_button.grid(row=3, column=0, columnspan=2, pady=10)

        # Frame principal (caché au début)
        self.main_frame = tk.Frame(self.root)

        # Frame de file d'attente
        self.queue_frame = tk.Frame(self.main_frame)
        self.queue_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.BOTH, expand=True)

        tk.Label(self.queue_frame, text="File d'attente", font=("Arial", 14, "bold")).pack(pady=5)

        self.queue_info = tk.Label(self.queue_frame, text="Joueurs en attente: 0")
        self.queue_info.pack(pady=5)

        self.queue_list = scrolledtext.ScrolledText(self.queue_frame, width=30, height=15)
        self.queue_list.pack(pady=5, fill=tk.BOTH, expand=True)
        self.queue_list.config(state=tk.DISABLED)

        self.join_queue_button = tk.Button(self.queue_frame, text="Rejoindre la file", command=self.join_queue)
        self.join_queue_button.pack(pady=5)

        self.leave_queue_button = tk.Button(self.queue_frame, text="Quitter la file", command=self.leave_queue, state=tk.DISABLED)
        self.leave_queue_button.pack(pady=5)

        # Frame de jeu
        self.game_frame = tk.Frame(self.main_frame)
        self.game_frame.pack(side=tk.RIGHT, padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.game_info = tk.Label(self.game_frame, text="En attente d'un match...", font=("Arial", 12))
        self.game_info.pack(pady=5)

        # Plateau de jeu
        self.board_frame = tk.Frame(self.game_frame)
        self.board_frame.pack(pady=10)

        self.buttons = []
        for i in range(3):
            for j in range(3):
                button = tk.Button(self.board_frame, text=" ", font=("Arial", 20, "bold"), width=3, height=1,
                                   command=lambda row=i, col=j: self.make_move(row * 3 + col))
                button.grid(row=i, column=j, padx=5, pady=5)
                self.buttons.append(button)

        # Désactiver le plateau au début
        self.disable_board()

        # Zone de chat
        tk.Label(self.game_frame, text="Chat", font=("Arial", 12)).pack(pady=5)

        self.chat_display = scrolledtext.ScrolledText(self.game_frame, width=40, height=10)
        self.chat_display.pack(pady=5, fill=tk.BOTH, expand=True)
        self.chat_display.config(state=tk.DISABLED)

        self.chat_frame = tk.Frame(self.game_frame)
        self.chat_frame.pack(fill=tk.X, pady=5)

        self.chat_entry = tk.Entry(self.chat_frame, width=30)
        self.chat_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.send_button = tk.Button(self.chat_frame, text="Envoyer", command=self.send_chat)
        self.send_button.pack(side=tk.RIGHT, padx=5)

        # Statistiques
        self.stats_frame = tk.Frame(self.game_frame)
        self.stats_frame.pack(pady=10, fill=tk.X)

        self.stats_label = tk.Label(self.stats_frame, text="Parties: 0 | Victoires: 0 | Défaites: 0")
        self.stats_label.pack()

        self.refresh_stats_button = tk.Button(self.stats_frame, text="Rafraîchir stats", command=self.get_stats)
        self.refresh_stats_button.pack(pady=5)

        # Gérer la fermeture de la fenêtre
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def start(self):
        self.root.mainloop()

    def connect(self):
        try:
            username = self.username_entry.get().strip()
            host = self.server_entry.get().strip()
            port = int(self.port_entry.get().strip())

            if not username:
                messagebox.showerror("Erreur", "Veuillez entrer un nom d'utilisateur")
                return

            self.username = username
            self.host = host
            self.port = port

            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.host, self.port))

            # Envoyer le nom d'utilisateur
            login_message = {
                "action": "login",
                "username": self.username
            }
            self.client_socket.send(json.dumps(login_message).encode('utf-8'))

            # Démarrer le thread d'écoute
            self.listen_thread = threading.Thread(target=self.listen_for_messages)
            self.listen_thread.daemon = True
            self.listen_thread.start()

            # Masquer le frame de connexion et afficher le frame principal
            self.login_frame.pack_forget()
            self.main_frame.pack(fill=tk.BOTH, expand=True)

            # Demander les statistiques
            self.get_stats()

        except Exception as e:
            messagebox.showerror("Erreur de connexion", str(e))

    def listen_for_messages(self):
        try:
            while True:
                data = self.client_socket.recv(1024).decode('utf-8')
                if not data:
                    break

                try:
                    message = json.loads(data)
                    action = message.get("action")

                    if action == "login_success":
                        self.player_id = message.get("player_id")

                    elif action == "joined_queue":
                        self.in_queue = True
                        self.join_queue_button.config(state=tk.DISABLED)
                        self.leave_queue_button.config(state=tk.NORMAL)

                    elif action == "left_queue":
                        self.in_queue = False
                        self.join_queue_button.config(state=tk.NORMAL)
                        self.leave_queue_button.config(state=tk.DISABLED)

                    elif action == "queue_update":
                        queue_length = message.get("queue_length", 0)
                        players = message.get("players", [])

                        self.queue_info.config(text=f"Joueurs en attente: {queue_length}")

                        self.queue_list.config(state=tk.NORMAL)
                        self.queue_list.delete(1.0, tk.END)

                        for i, player in enumerate(players, 1):
                            self.queue_list.insert(tk.END, f"{i}. {player['username']} (depuis {player['join_time']})\n")

                        self.queue_list.config(state=tk.DISABLED)

                    elif action == "game_start":
                        self.in_game = True
                        self.in_queue = False
                        self.opponent = message.get("opponent")
                        self.symbol = message.get("symbol")
                        self.my_turn = message.get("your_turn")

                        # Mettre à jour les informations
                        self.game_info.config(text=f"Match contre {self.opponent} - Vous êtes {self.symbol}")

                        if self.my_turn:
                            self.enable_board()
                        else:
                            self.disable_board()

                        # Effacer le chat
                        self.chat_display.config(state=tk.NORMAL)
                        self.chat_display.delete(1.0, tk.END)
                        self.chat_display.config(state=tk.DISABLED)

                    elif action == "game_update":
                        game_state = message.get("game_state", {})
                        board = game_state.get("board", [" " for _ in range(9)])
                        self.my_turn = game_state.get("current_turn") == self.username

                        # Mettre à jour le plateau
                        self.board = board
                        for i in range(9):
                            self.buttons[i].config(text=board[i])

                        if self.my_turn and not game_state.get("finished", False):
                            self.enable_board()
                            self.game_info.config(text=f"C'est votre tour - Vous êtes {self.symbol}")
                        else:
                            self.disable_board()
                            if not game_state.get("finished", False):
                                self.game_info.config(text=f"Tour de {self.opponent} - Vous êtes {self.symbol}")

                    elif action == "game_over":
                        winner = message.get("winner")
                        game_message = message.get("message")

                        self.game_info.config(text=game_message)
                        messagebox.showinfo("Fin de partie", game_message)

                        # Réinitialiser l'état
                        self.in_game = False
                        self.join_queue_button.config(state=tk.NORMAL)
                        self.disable_board()

                        # Mettre à jour les statistiques
                        self.get_stats()

                    elif action == "chat_message":
                        from_player = message.get("from")
                        msg = message.get("message")
                        time_str = message.get("time")

                        self.chat_display.config(state=tk.NORMAL)
                        self.chat_display.insert(tk.END, f"[{time_str}] {from_player}: {msg}\n")
                        self.chat_display.see(tk.END)
                        self.chat_display.config(state=tk.DISABLED)

                    elif action == "stats":
                        total_games = message.get("total_games", 0)
                        wins = message.get("wins", 0)
                        losses = message.get("losses", 0)

                        self.stats_label.config(text=f"Parties: {total_games} | Victoires: {wins} | Défaites: {losses}")

                    elif action == "error":
                        error_message = message.get("message", "Une erreur s'est produite")
                        messagebox.showerror("Erreur", error_message)

                except json.JSONDecodeError:
                    print(f"Données invalides reçues: {data}")

        except Exception as e:
            if self.client_socket:
                messagebox.showerror("Erreur de connexion", f"Déconnecté du serveur: {str(e)}")
                self.client_socket.close()
                self.client_socket = None

    def join_queue(self):
        if not self.client_socket:
            messagebox.showerror("Erreur", "Non connecté au serveur")
            return

        if self.in_queue:
            messagebox.showinfo("Info", "Vous êtes déjà dans la file d'attente")
            return

        join_message = {"action": "join_queue"}
        self.client_socket.send(json.dumps(join_message).encode('utf-8'))

    def leave_queue(self):
        if not self.client_socket:
            messagebox.showerror("Erreur", "Non connecté au serveur")
            return

        if not self.in_queue:
            messagebox.showinfo("Info", "Vous n'êtes pas dans la file d'attente")
            return

        leave_message = {"action": "leave_queue"}
        self.client_socket.send(json.dumps(leave_message).encode('utf-8'))

    def make_move(self, position):
        if not self.client_socket or not self.in_game or not self.my_turn:
            return

        if self.board[position] != " ":
            return

        move_message = {
            "action": "make_move",
            "position": position
        }
        self.client_socket.send(json.dumps(move_message).encode('utf-8'))

        # Désactiver le plateau en attendant la réponse du serveur
        self.disable_board()

    def send_chat(self):
        if not self.client_socket or not self.in_game:
            messagebox.showinfo("Info", "Vous n'êtes pas dans un match")
            return

        message = self.chat_entry.get().strip()
        if not message:
            return

        chat_message = {
            "action": "chat_message",
            "message": message
        }
        self.client_socket.send(json.dumps(chat_message).encode('utf-8'))

        # Ajouter le message au chat
        time_str = datetime.now().strftime("%H:%M:%S")
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"[{time_str}] Vous: {message}\n")
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

        # Effacer l'entrée
        self.chat_entry.delete(0, tk.END)

    def get_stats(self):
        if not self.client_socket:
            return

        stats_message = {"action": "get_stats"}
        self.client_socket.send(json.dumps(stats_message).encode('utf-8'))

    def enable_board(self):
        for i in range(9):
            if self.board[i] == " ":
                self.buttons[i].config(state=tk.NORMAL)

    def disable_board(self):
        for button in self.buttons:
            button.config(state=tk.DISABLED)

    def on_close(self):
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        self.root.destroy()

if __name__ == "__main__":
    client = TicTacToeClient()
    client.start()