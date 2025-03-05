import tkinter
import os
import webbrowser


__version__ = "1.0.0"
website = "http://localhost:8000"

class app:
    def __init__(self):
        tk = tkinter.Tk()
        tk.title("Deployment Center")
        tk.geometry("400x400")
        tk.resizable(False, False)
        self.main()
        tk.mainloop()
    
    def main(self):
        label_title = tkinter.Label(text="Deployment Center")
        label_title.pack()
        label_title.config(font=("Arial", 20))

        frame_deploy = tkinter.Frame()
        frame_deploy.place(x=50, y=50)
        label_deploy = tkinter.Label(frame_deploy, text="Deployment")
        label_deploy.pack()
        button_deploy = tkinter.Button(frame_deploy, text="Deploy", command=self.deploy)
        button_deploy.pack()
        label_web_online = tkinter.Label(frame_deploy, text="Web Online")
        label_web_online.pack()
        button_web_online = tkinter.Button(frame_deploy, text="Open", command=self.open_web_online)
        button_web_online.pack()

        frame_config = tkinter.Frame()
        frame_config.place(x=250, y=50)
        label_config = tkinter.Label(frame_config, text="Configuration")
        label_config.pack()
        button_config = tkinter.Button(frame_config, text="Config", command=self.config)
        button_config.pack()
        label_web_config = tkinter.Label(frame_config, text="Web Config")
        label_web_config.pack()
        button_web_config = tkinter.Button(frame_config, text="Open file", command=self.open_file_web_config)
        button_web_config.pack()

        label_version = tkinter.Label(text="Version: {}".format(__version__))
        label_version.place(x=150, y=380)
        label_version.config(font=("Arial", 10), fg="blue")

    def deploy(self):
        pass

    def open_web_online(self):
        webbrowser.open(website)

    def config(self):
        pass

    def open_file_web_config(self):
        pass


if __name__ == "__main__":
    app()