"""Parse ESO Lua saved variable files into Python dicts."""
import re

# Single-pass tokenizer: strip comments then tokenize
_RE_COMMENT = re.compile(r'--[^\n]*')
_RE_TOKEN   = re.compile(
    r'"(?:[^"\\]|\\.)*"'   # string
    r'|[{}\[\]=,]'         # punctuation
    r'|[+-]?\d+\.?\d*(?:[eE][+-]?\d+)?'  # number
    r'|true|false|nil'     # keywords
    r'|[a-zA-Z_]\w*'       # identifier
)


class LuaParser:
    def __init__(self, tokens: list[str]):
        self._t   = tokens
        self._pos = 0

    def _peek(self) -> str | None:
        return self._t[self._pos] if self._pos < len(self._t) else None

    def _next(self) -> str:
        t = self._t[self._pos]
        self._pos += 1
        return t

    def _value(self):
        tok = self._peek()
        if tok is None:
            return None
        if tok == '{':
            return self._table()
        self._pos += 1
        if tok.startswith('"'):
            return tok[1:-1].replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
        if tok == 'true':  return True
        if tok == 'false': return False
        if tok == 'nil':   return None
        # number
        try:
            return float(tok) if ('.' in tok or 'e' in tok.lower()) else int(tok)
        except ValueError:
            return tok  # bare identifier

    def _table(self):
        self._pos += 1  # {
        result = {}
        seq    = 1
        while True:
            tok = self._peek()
            if tok is None or tok == '}':
                self._pos += 1
                break
            if tok == '[':
                self._pos += 1          # [
                key = self._value()
                self._pos += 1          # ]
                self._pos += 1          # =
            else:
                # could be "ident =" or sequential value
                if self._pos + 1 < len(self._t) and self._t[self._pos + 1] == '=':
                    key = tok
                    self._pos += 2      # ident =
                else:
                    key = seq
                    seq += 1
            result[key] = self._value()
            if self._peek() == ',':
                self._pos += 1
        # convert sequential int-keyed dict to list
        if result and all(isinstance(k, int) for k in result) and \
                set(result) == set(range(1, len(result) + 1)):
            return [result[i] for i in range(1, len(result) + 1)]
        return result

    def parse(self) -> dict:
        out = {}
        while self._pos < len(self._t):
            name = self._next()         # variable name
            self._pos += 1              # =
            out[name] = self._value()
        return out


def load(text: str) -> dict:
    clean  = _RE_COMMENT.sub('', text)
    tokens = _RE_TOKEN.findall(clean)
    return LuaParser(tokens).parse()
