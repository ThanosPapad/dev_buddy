import tkinter as tk
from gui import SerialConnectionApp

def main():
    # Create the main application window
    root = tk.Tk()
    
    app = SerialConnectionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
