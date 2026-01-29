from GUI import App

def main():
    # Disable scanning completely if you want (avoids any COM port queries)
    app = App(tick_ms=25, scan_serial_ports=False)
    app.mainloop()

if __name__ == "__main__":
    main()
