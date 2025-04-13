import mysql.connector

class Database:
    def __init__(self):
        self.connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="morpion_game"
        )
        self.cursor = self.connection.cursor()

    def close(self):
        self.cursor.close()
        self.connection.close()

    def add_player(self, username):
        query = "INSERT INTO players (username) VALUES (%s)"
        self.cursor.execute(query, (username,))
        self.connection.commit()
        return self.cursor.lastrowid

    def get_player_by_username(self, username):
        query = "SELECT * FROM players WHERE username = %s"
        self.cursor.execute(query, (username,))
        return self.cursor.fetchone()

    def get_player_by_id(self, player_id):
        query = "SELECT * FROM players WHERE id = %s"
        self.cursor.execute(query, (player_id,))
        return self.cursor.fetchone()

    def update_elo(self, player_id, new_elo):
        query = "UPDATE players SET elo = %s WHERE id = %s"
        self.cursor.execute(query, (new_elo, player_id))
        self.connection.commit()

    def create_game(self, player1_id, player2_id):
        query = "INSERT INTO games (player1_id, player2_id) VALUES (%s, %s)"
        self.cursor.execute(query, (player1_id, player2_id))
        self.connection.commit()
        return self.cursor.lastrowid

    def update_game_winner(self, game_id, winner_id, turns_count):
        query = "UPDATE games SET winner_id = %s, turns_count = %s WHERE id = %s"
        self.cursor.execute(query, (winner_id, turns_count, game_id))
        self.connection.commit()

    def get_player_stats(self, player_id):
        query = """
        SELECT COUNT(*) as total_games,
        SUM(CASE WHEN winner_id = %s THEN 1 ELSE 0 END) as wins
        FROM games
        WHERE player1_id = %s OR player2_id = %s
        """
        self.cursor.execute(query, (player_id, player_id, player_id))
        result = self.cursor.fetchone()
        if result:
            total_games, wins = result
            wins = wins if wins is not None else 0
            return (total_games, wins)
        return (0, 0)