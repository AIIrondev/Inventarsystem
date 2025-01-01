import tkinter as tk
from database import Database as db
from database import Register_Database as rdb

class UI:
    def __init__(self):
        self.app = tk.Tk()
        self.app.title('Inventory')
        self.app.geometry('400x400')
        self.app.resizable(True, True)
        self.main()
        self.app.mainloop()

    def main(self):
        tk.Label(self.app, text='Inventory').place(x=200, y=30, anchor='center')
        tk.Label(self.app, text='New').place(x=50, y=80)
        tk.Label(self.app, text='Modify').place(x=180, y=80)
        tk.Label(self.app, text='Delete').place(x=310, y=80)


if __name__ == '__main__':
    UI()