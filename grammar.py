import lark

parser = lark.Lark.open("grammar.lark", parser='lalr')
