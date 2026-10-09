
#FGBFIX

Es la solucion para reparar las boletas mal generadas que se bajan de Federacion Gráfica Bonaerense.
Implementa vecfixer para reparar la boleta en si y fgb_campovence para recrear el campo con widgets de fecha.
Depende de pypdf y de python3-tk. 

para instalar las dependencias:

```
    sudo apt install python3-tk #en caso de usar debian/ubuntu

    python3 -m venv venv-fgbfix
    source venv-fgbfix/bin/activate
    python3 -m pip install -r requirements-python-3.13.5.txt
    deactivate

```

para ejecutar fgbfix.py:

```
    source venv-fgbfix/bin/activate
    python3 fgbfix.py
```

