import uvicorn
import sys

if __name__ == "__main__":
    port = 8000
    host = "0.0.0.0"
    reload_flag = False  # Por defecto: modo producción estable (sin auto-reload)

    args = sys.argv[1:]
    if len(args) > 0:
        for a in args:
            if a.lower() in ("--reload", "-r"):
                reload_flag = True
            elif a.lstrip("-").replace(".", "").isdigit():
                try:
                    port = int(a)
                except ValueError:
                    pass

    print(f"Iniciando Webdom Monitor en {host}:{port}")
    print(f"Documentacion API: http://{host}:{port}/docs")
    if reload_flag:
        print("Modo DESARROLLO (auto-reload activado)")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload_flag,
        log_level="info"
    )
