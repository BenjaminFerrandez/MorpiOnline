import socket
import threading
import json
import tkinter as tk
from tkinter import messagebox


class TicTacToeClient:
    def __init__(self, host="localhost", port=5555):
        self.host = host
        self.port = port
        self.client_socket = None
        self.client_id = None
        self.game_id = None
        self.player_symbol = None
        self.opponent_id = None
        self.current_player = None
        self.board = [" " for _ in range(9)]
        self.game_over = False
        self.has_requested_rematch = False

        # Interface graphique
        self.root = tk.Tk()
        self.root.title("Tic-Tac-Toe Client")
        self.root.geometry("400x550")
        self.root.resizable(False, False)

        # Statut
        self.status_frame = tk.Frame(self.root)
        self.status_frame.pack(pady=10)

        self.status_label = tk.Label(self.status_frame, text="Connexion au serveur...", font=("Arial", 12))
        self.status_label.pack()

        # Plateau de jeu
        self.board_frame = tk.Frame(self.root)
        self.board_frame.pack(pady=10)

        self.buttons = []
        for i in range(3):
            for j in range(3):
                idx = i * 3 + j
                button = tk.Button(self.board_frame, text=" ", font=("Arial", 20, "bold"),
                                   width=5, height=2, command=lambda pos=idx: self.make_move(pos))
                button.grid(row=i, column=j, padx=5, pady=5)
                self.buttons.append(button)

        # Bouton de revanche
        self.control_frame = tk.Frame(self.root)
        self.control_frame.pack(pady=10)

        self.rematch_button = tk.Button(self.control_frame, text="Demander une revanche",
                                        font=("Arial", 12), command=self.request_rematch, state="disabled")
        self.rematch_button.pack(pady=10)

        self.rematch_status = tk.Label(self.control_frame, text="", font=("Arial", 10))
        self.rematch_status.pack(pady=5)

        # Désactive les boutons au démarrage
        self.set_board_enabled(False)

        # Connexion au serveur
        self.connect_to_server()

        # Démarre la boucle principale
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def connect_to_server(self):
        """Établit la connexion avec le serveur"""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.host, self.port))

            # Démarre le thread de réception
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()

            self.status_label.config(text="Connecté. En attente d'un adversaire...")
        except Exception as e:
            self.status_label.config(text=f"Erreur de connexion: {e}")

    def receive_messages(self):
        """Reçoit les messages du serveur"""
        buffer = ""

        while True:
            try:
                data = self.client_socket.recv(1024).decode('utf-8')
                if not data:
                    break

                buffer += data

                # Traite chaque message complet
                while "\n" in buffer:
                    message, buffer = buffer.split("\n", 1)
                    try:
                        message_data = json.loads(message)
                        # Utilise la méthode update_ui pour mettre à jour l'interface
                        self.root.after(0, lambda msg=message_data: self.update_ui(msg))
                    except json.JSONDecodeError:
                        print(f"JSON invalide: {message}")

            except Exception as e:
                print(f"Erreur de réception: {e}")
                break

        # Si on sort de la boucle, c'est que la connexion a été perdue
        self.root.after(0, lambda: self.status_label.config(text="Connexion au serveur perdue"))
        self.root.after(0, lambda: self.set_board_enabled(False))
        self.root.after(0, lambda: self.rematch_button.config(state="disabled"))

    def update_ui(self, message):
        """Met à jour l'interface utilisateur en fonction du message reçu"""
        message_type = message.get("type")

        if message_type == "connection":
            self.client_id = message.get("client_id")
            self.status_label.config(text=f"Connecté. ID: {self.client_id[:8]}... En attente d'un adversaire...")
            self.has_requested_rematch = False
            self.rematch_button.config(state="disabled")
            self.rematch_status.config(text="")

        elif message_type == "game_start":
            self.game_id = message.get("game_id")
            self.player_symbol = message.get("player_symbol")
            self.opponent_id = message.get("opponent_id")
            self.status_label.config(text=f"Partie trouvée! Vous êtes {self.player_symbol}")
            self.has_requested_rematch = False
            self.rematch_button.config(state="disabled")
            self.rematch_status.config(text="")

        elif message_type == "game_state":
            state = message.get("state")
            if not state:
                return

            self.board = state.get("board")
            self.current_player = state.get("current_player")
            self.game_over = state.get("game_over")

            # Met à jour le plateau
            for i, cell in enumerate(self.board):
                self.buttons[i].config(text=cell)

            # Met à jour le statut et les contrôles de revanche
            if state.get("is_draw") or state.get("winner"):
                self.rematch_button.config(state="normal")

                # Affiche les demandes de revanche
                rematch_requests = state.get("rematch_requests", [])
                if rematch_requests:
                    if self.client_id in rematch_requests and len(rematch_requests) == 1:
                        self.rematch_status.config(text="Vous avez demandé une revanche. En attente de l'adversaire...")
                    elif self.client_id not in rematch_requests:
                        self.rematch_status.config(text="Votre adversaire demande une revanche!")
                    elif len(rematch_requests) == 2:
                        self.rematch_status.config(text="Les deux joueurs ont accepté la revanche!")

                # Met à jour le statut de fin de partie
                if state.get("is_draw"):
                    self.status_label.config(text="Match nul!")
                elif state.get("winner"):
                    if state.get("winner") == message.get("your_symbol"):
                        self.status_label.config(text="Vous avez gagné!")
                    else:
                        self.status_label.config(text="Vous avez perdu!")

                self.set_board_enabled(False)
            else:
                self.rematch_button.config(state="disabled")
                self.rematch_status.config(text="")

                if self.current_player == message.get("your_symbol"):
                    self.status_label.config(text="C'est votre tour")
                    self.set_board_enabled(True)
                else:
                    self.status_label.config(text="Tour de l'adversaire")
                    self.set_board_enabled(False)

        elif message_type == "opponent_disconnected":
            messagebox.showinfo("Information", "Votre adversaire s'est déconnecté. Retour à la file d'attente.")
            self.status_label.config(text="En attente d'un nouvel adversaire...")
            self.set_board_enabled(False)
            self.rematch_button.config(state="disabled")
            self.rematch_status.config(text="")
            self.has_requested_rematch = False

            # Réinitialise le plateau
            for button in self.buttons:
                button.config(text=" ")

        elif message_type == "rematch_accepted":
            self.player_symbol = message.get("player_symbol")
            self.status_label.config(text=f"Revanche! Vous êtes maintenant {self.player_symbol}")
            self.has_requested_rematch = False
            self.rematch_button.config(state="disabled")
            self.rematch_status.config(text="")

            # Réinitialise le plateau visuel
            for button in self.buttons:
                button.config(text=" ")

        elif message_type == "error":
            messagebox.showerror("Erreur", message.get("message", "Une erreur s'est produite"))

    def make_move(self, position):
        """Envoie un mouvement au serveur"""
        if self.game_over or self.board[position] != " ":
            return

        try:
            message = {
                "type": "move",
                "position": position
            }
            self.send_message(message)
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur d'envoi: {e}")

    def request_rematch(self):
        """Envoie une demande de revanche au serveur"""
        if not self.game_over:
            return

        try:
            message = {
                "type": "rematch_request"
            }
            self.send_message(message)
            self.has_requested_rematch = True
            self.rematch_button.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur d'envoi: {e}")

    def send_message(self, message):
        """Envoie un message au serveur"""
        if not self.client_socket:
            return

        try:
            self.client_socket.sendall(json.dumps(message).encode('utf-8'))
        except Exception as e:
            print(f"Erreur d'envoi: {e}")

    def set_board_enabled(self, enabled):
        """Active ou désactive le plateau de jeu"""
        state = "normal" if enabled else "disabled"
        for i, button in enumerate(self.buttons):
            if self.board[i] == " ":  # Ne modifie que les cases vides
                button.config(state=state)

    def on_close(self):
        """Gère la fermeture de l'application"""
        try:
            if self.client_socket:
                self.client_socket.close()
        except:
            pass
        self.root.destroy()


if __name__ == "__main__":
    client = TicTacToeClient()