import sqlite3

class Database:
    def __init__(self) -> None:
        self.conn = sqlite3.connect('elios.sqlite')
        self.cur = self.conn.cursor()

        #self.cur.execute('CREATE TABLE registrations(id_registrations, author_id, ingame_name, forum_name, pictures_contest, pictures_ign)')
        #self.conn.commit()

    def execute(self, query, *args):
        self.cur.execute(query, args)
        self.conn.commit()

    def query(self, query, *args): 
        self.cur.execute(query, args) 
        return self.cur.fetchall()