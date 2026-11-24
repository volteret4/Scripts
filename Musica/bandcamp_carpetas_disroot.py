#!/usr/bin/env python3
"""Recrea en el buzón IMAP las carpetas a las que movían los avisos de Bandcamp
las reglas de Thunderbird, y aplica esas reglas a la bandeja de entrada.

Lee msgFilterRules.dat de la cuenta, se queda con las reglas de tipo
«Move to folder» cuyo destino está bajo Musica/ (activas o no) y cuyas condiciones son de
remitente o asunto (is / contains / begins with), y para cada correo de INBOX
que cumple una regla: le pone las etiquetas que añade la regla (p. ej. $label3)
y lo mueve a su carpeta. Las reglas se aplican en orden y gana la primera, como
en Thunderbird.

Sin --aplicar solo enseña lo que haría. La contraseña se pide por teclado y no
se guarda.

  python3 bandcamp_carpetas_disroot.py
  python3 bandcamp_carpetas_disroot.py --aplicar
"""
import argparse
import email.header
import email.utils
import getpass
import imaplib
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PERFIL = Path.home() / '.thunderbird/9iyguy1b.default-release'
REGLAS = PERFIL / 'ImapMail/disroot.org/msgFilterRules.dat'
SERVIDOR, PUERTO = 'disroot.org', 993
USUARIO = 'frodobolson@disroot.org'
RAIZ = 'Musica/'


def leer_reglas(path):
    """Bloques name=… seguidos de sus claves; action/actionValue van por pares."""
    reglas, r = [], None
    for linea in path.read_text(encoding='utf-8', errors='replace').splitlines():
        m = re.match(r'(\w+)="(.*)"$', linea)
        if not m:
            continue
        k, v = m.groups()
        if k == 'name':
            r = {'name': v, 'actions': []}
            reglas.append(r)
        elif r is None:
            continue
        elif k == 'action':
            r['actions'].append([v, None])
        elif k == 'actionValue' and r['actions']:
            r['actions'][-1][1] = v
        else:
            r[k] = v
    return reglas


TERM = re.compile(r'(AND|OR) \((from|subject|[^,]+),([^,]+),(.*?)\)(?= AND \(| OR \(|$)')


def condiciones(cond):
    """[(op_lógico, campo, operador, valor)] o None si hay algo que no sabemos evaluar."""
    terms = TERM.findall(cond.strip())
    if not terms or ' '.join(f'{a} ({b},{c},{d})' for a, b, c, d in terms) != cond.strip():
        return None
    if any(campo not in ('from', 'subject') or op not in ('is', 'contains', 'begins with') for _, campo, op, _ in terms):
        return None
    return terms


def cumple(terms, cabeceras):
    def uno(campo, op, valor):
        texto = cabeceras[campo].lower()
        valor = valor.lower()
        if campo == 'from' and op == 'is':
            return valor == cabeceras['from_addr'].lower() or valor == texto
        return {'is': texto == valor, 'contains': valor in texto, 'begins with': texto.startswith(valor)}[op]
    res = [uno(c, o, v) for _, c, o, v in terms]
    return any(res) if terms[0][0] == 'OR' else all(res)


def decodificar(h):
    partes = []
    for txt, enc in email.header.decode_header(h or ''):
        partes.append(txt.decode(enc or 'utf-8', errors='replace') if isinstance(txt, bytes) else txt)
    return ''.join(partes).replace('\r', '').replace('\n', ' ').strip()


def imap_quote(nombre):
    return '"' + nombre.replace('\\', '\\\\').replace('"', '\\"') + '"'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--aplicar', action='store_true', help='crear carpetas y mover correos (sin esto, solo lo enseña)')
    ap.add_argument('--origen', default='INBOX', help='carpeta en la que buscar (por defecto INBOX)')
    a = ap.parse_args()

    # También las desactivadas: Thunderbird desactiva solo los filtros cuya carpeta destino desaparece.
    reglas, desactivadas = [], []
    for r in leer_reglas(REGLAS):
        destinos = [v for act, v in r['actions'] if act == 'Move to folder' and v and f'/{RAIZ}' in v]
        if not destinos:
            continue
        terms = condiciones(r.get('condition', ''))
        if terms is None:
            print(f'  · se omite «{r["name"]}»: condición que este script no evalúa')
            continue
        carpeta = destinos[0].split('disroot.org/', 1)[1]
        etiquetas = [v for act, v in r['actions'] if act == 'AddTag' and v]
        reglas.append((r['name'], terms, carpeta, etiquetas))
        if r.get('enabled') != 'yes':
            desactivadas.append(r['name'])
    carpetas = sorted({c for _, _, c, _ in reglas})
    print(f'{len(reglas)} reglas aplicables, {len(carpetas)} carpetas destino.')
    if desactivadas:
        print(f'  ({len(desactivadas)} estaban desactivadas en Thunderbird; actívalas allí cuando existan las carpetas)')

    imap = imaplib.IMAP4_SSL(SERVIDOR, PUERTO)
    imap.login(USUARIO, getpass.getpass(f'Contraseña IMAP de {USUARIO}: '))

    _, lista = imap.list()
    existentes = set()
    sep = '/'
    for l in lista or []:
        m = re.match(rb'\((.*?)\) "(.*?)" (.*)$', l)
        if m:
            sep = m.group(2).decode() or sep
            existentes.add(m.group(3).decode().strip('"'))
    faltan = [c for c in carpetas if c.replace('/', sep) not in existentes]
    print(f'\nCarpetas que faltan ({len(faltan)}):', *[f'  {c}' for c in faltan] or ['  ninguna'], sep='\n')
    if a.aplicar:
        # Primero los padres (Musica, Musica/Jazz…) para servidores que no los crean solos.
        nuevas = sorted({sep.join(c.split('/')[:i]) for c in faltan for i in range(1, c.count('/') + 2)} - existentes, key=len)
        for c in nuevas:
            typ, msg = imap.create(imap_quote(c))
            imap.subscribe(imap_quote(c))
            print(f'  creada {c}: {typ}')

    typ, _ = imap.select(imap_quote(a.origen), readonly=not a.aplicar)
    if typ != 'OK':
        sys.exit(f'No se puede abrir {a.origen}')
    _, data = imap.uid('SEARCH', None, 'ALL')
    uids = data[0].split()
    print(f'\n{len(uids)} correos en {a.origen}; leyendo remitente y asunto…')
    por_carpeta, por_regla = defaultdict(list), Counter()
    for i in range(0, len(uids), 500):
        lote = b','.join(uids[i:i + 500])
        _, resp = imap.uid('FETCH', lote, '(UID BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])')
        for item in resp:
            if not isinstance(item, tuple):
                continue
            uid = re.search(rb'UID (\d+)', item[0]).group(1)
            msg = email.message_from_bytes(item[1])
            frm = decodificar(msg.get('From'))
            cab = {'from': frm, 'from_addr': email.utils.parseaddr(frm)[1], 'subject': decodificar(msg.get('Subject'))}
            for nombre, terms, carpeta, etiquetas in reglas:
                if cumple(terms, cab):
                    por_carpeta[(carpeta, tuple(etiquetas))].append(uid)
                    por_regla[nombre] += 1
                    break

    total = sum(len(v) for v in por_carpeta.values())
    print(f'\n{total} correos casan con alguna regla:')
    for (carpeta, _), us in sorted(por_carpeta.items()):
        print(f'  {len(us):5}  → {carpeta}')
    if not a.aplicar:
        print('\nNo se ha cambiado nada. Repite con --aplicar para crear las carpetas y mover los correos.')
        imap.logout()
        return

    soporta_move = b'MOVE' in b' '.join(imap.capabilities if isinstance(imap.capabilities[0], bytes) else [c.encode() for c in imap.capabilities])
    for (carpeta, etiquetas), us in sorted(por_carpeta.items()):
        destino = imap_quote(carpeta.replace('/', sep))
        for i in range(0, len(us), 200):
            lote = b','.join(us[i:i + 200]).decode()
            if etiquetas:
                imap.uid('STORE', lote, '+FLAGS', '(' + ' '.join(etiquetas) + ')')
            if soporta_move:
                typ, _ = imap.uid('MOVE', lote, destino)
            else:
                typ, _ = imap.uid('COPY', lote, destino)
                if typ == 'OK':
                    imap.uid('STORE', lote, '+FLAGS', r'(\Deleted)')
            if typ != 'OK':
                print(f'  ⚠ no se pudo mover a {carpeta}: {typ}')
        print(f'  movidos {len(us)} → {carpeta}')
    if not soporta_move:
        imap.expunge()
    imap.logout()
    print('\nHecho. Para el servicio bandcamp, IMAP_FOLDERS debe listar estas carpetas (carpeta:género).')


if __name__ == '__main__':
    main()
