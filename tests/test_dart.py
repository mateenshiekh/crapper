from pathlib import Path

from crapper.languages.dart import functions_in_source, library_namespace


def _write(root: Path, relative: str, source: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_functions_members_and_every_decision_kind():
    source = """
int top(int a, int b) {
  if (a > 0) {
    return 1;
  } else if (b > 0) {
    return 2;
  }
  return 3;
}
int get counter => 1;
set counter(int v) {}
String arrow(int x) => x > 1 && x < 3 && x != 2 ? 'a' : 'b';
Future<void> stream(Stream<int> s) async { await for (final x in s) {} }
final f = (int x) => x;

class A {
  A(this.x) : y = x ?? 0;
  const A.named({required this.x}) : y = 0;
  factory A.fromJson(Map m) { if (m['a'] == null) { return A(1); } return A(m['a']); }
  A.redirect() : this(1);
  final int? x;
  final int y;
  @override
  int run() { return x!; }
  static int fill(int? a) { a ??= 2; return a; }
  bool operator ==(Object o) => o is A && o.x == x;
  void chains(A? o) { var z = o?.x ?? o?.y ?? 0; o?.run(); final l = o?[0]; o?..run(); }
  void loops() { do {} while (true); for (var i = 0; i < 1; i++) {} }
  void tries() { try {} on E {} on F catch (e) {} catch (e, st) {} finally {} }
  void sw(int v) { switch (v) { case 1: case 2: break; case int n when n > 5: break; default: break; } }
  String swe(Object v) => switch (v) { int n when n > 0 => 'p', int() => 'i', _ => 'o' };
  void elements(Object v) { if (v case int n) {} final l = [if (v is int) 1 else 2, for (var i in []) i]; }
  void nested() {
    int inner(int q) { if (q > 0) return 1; return 0; }
    final cb = () { if (true) {} };
    list.where((e) => e != null || e == 1);
  }
}
mixin M { int mix() { if (true) return 1; return 0; } }
enum E { a, b; int val() { return this == E.a ? 1 : 2; } }
extension Ext on int { int twice() => this * 2; int get half => this ~/ 2; }
"""
    functions = functions_in_source(source, "lib/demo/sample.dart", "/proj")
    assert [(fn.namespace, fn.name, fn.complexity) for fn in functions] == [
        ("demo.sample", "top", 3),
        ("demo.sample", "counter", 1),
        ("demo.sample", "counter=", 1),
        ("demo.sample", "arrow", 4),
        ("demo.sample", "stream", 2),
        ("demo.sample.A", "A.fromJson", 2),
        ("demo.sample.A", "run", 1),
        ("demo.sample.A", "fill", 2),
        ("demo.sample.A", "operator ==", 2),
        ("demo.sample.A", "chains", 8),
        ("demo.sample.A", "loops", 3),
        ("demo.sample.A", "tries", 4),
        ("demo.sample.A", "sw", 5),
        ("demo.sample.A", "swe", 4),
        ("demo.sample.A", "elements", 4),
        ("demo.sample.A", "nested", 4),
        ("demo.sample.M", "mix", 2),
        ("demo.sample.E", "val", 2),
        ("demo.sample.Ext", "twice", 1),
        ("demo.sample.Ext", "half", 1),
    ]


def test_bodied_constructors_operators_and_extension_types():
    source = """
class C {
  C(this.x) : y = x ?? 0 { if (x == null) {} }
  C.n() {}
  factory C.f() => C(1);
  static int get sg => 1;
  static set ss(int v) {}
  late final cb = () { if (true) {} };
  int operator [](int i) => i;
  void operator []=(int i, int v) {}
  C operator -() => this;
  (int, String) rec() => (1, 'a');
}
extension type Id(int v) { int plus() { if (v > 0) return v; return 0; } }
enum Planet { earth(1); const Planet(this.m); final int m; int g() { return m; } }
extension on String { int lenOrZero() => isEmpty ? 0 : length; }
int Function() maker() => () => 1;
"""
    functions = functions_in_source(source, "lib/c.dart", "/proj")
    assert [(fn.namespace, fn.name, fn.complexity) for fn in functions] == [
        ("c.C", "C", 3),
        ("c.C", "C.n", 1),
        ("c.C", "C.f", 1),
        ("c.C", "sg", 1),
        ("c.C", "ss=", 1),
        ("c.C", "operator []", 1),
        ("c.C", "operator []=", 1),
        ("c.C", "operator -", 1),
        ("c.C", "rec", 1),
        ("c.Id", "plus", 2),
        ("c.Planet", "g", 1),
        ("c", "lenOrZero", 2),
        ("c", "maker", 1),
    ]


def test_declarations_without_a_body_are_not_entries():
    source = """
external int ext();
abstract class Base {
  int run();
  external int native();
  Base();
  const Base.k();
  factory Base.make() = Impl;
}
class Widget {
  const Widget({required this.title, this.count = 0});
  final String title;
  final int count;
}
"""
    assert functions_in_source(source, "lib/base.dart", "/proj") == []


def test_spans_cover_signature_and_body_and_skip_a_comment_between_them():
    source = "int\nplus(int a) /* doc */ {\n  return a + 1;\n}\n"
    found = functions_in_source(source, "lib/m.dart", "/proj")
    assert len(found) == 1
    fn = found[0]
    assert (fn.start_line, fn.end_line) == (1, 4)
    assert source[fn.start_byte : fn.end_byte] == "int\nplus(int a) /* doc */ {\n  return a + 1;\n}"
    assert fn.language == "dart"


def test_strings_and_comments_do_not_add_decisions():
    source = """
String literal(String name) {
  // if (name) ?? while
  /* for && || ?. */
  return 'if $name and ?? or';
}
String interpolated(bool ok) => 'value: ${ok ? 1 : 0}';
"""
    functions = functions_in_source(source, "lib/text.dart", "/proj")
    assert [(fn.name, fn.complexity) for fn in functions] == [("literal", 1), ("interpolated", 2)]


def test_namespace_is_the_package_name_plus_the_path_under_lib(tmp_path):
    _write(tmp_path, "pubspec.yaml", "name: shop\ndescription: demo\n")
    _write(tmp_path, "lib/src/cart.dart", "int total() => 1;\n")
    _write(tmp_path, "lib/main.dart", "void main() {}\n")
    _write(tmp_path, "bin/tool.dart", "void main() {}\n")
    _write(tmp_path, "packages/ui/pubspec.yaml", 'name: "ui"\n')
    _write(tmp_path, "packages/ui/lib/button.dart", "class Button { int press() => 1; }\n")
    root = str(tmp_path)

    def namespace(relative: str) -> str:
        source = (tmp_path / relative).read_text(encoding="utf-8")
        return functions_in_source(source, relative, root)[0].namespace

    assert namespace("lib/src/cart.dart") == "shop.src.cart"
    assert namespace("lib/main.dart") == "shop.main"
    assert namespace("bin/tool.dart") == "shop.bin.tool"
    assert namespace("packages/ui/lib/button.dart") == "ui.button.Button"


def test_namespace_without_a_pubspec_is_the_path_under_lib():
    assert library_namespace("lib/app/view.dart", None) == "app.view"
    assert library_namespace("/proj/lib/view.dart", "/proj") == "view"
    assert library_namespace("./lib/view.dart", ".") == "view"
    assert library_namespace("tool/gen.dart", "/proj") == "tool.gen"
    assert library_namespace("packages/ui/lib/button.dart", None) == "button"


def test_a_pubspec_without_a_name_falls_back_to_the_path(tmp_path):
    _write(tmp_path, "pubspec.yaml", "description: nameless\n")
    source = _write(tmp_path, "lib/a.dart", "int f() => 1;\n")
    assert library_namespace("lib/a.dart", str(tmp_path)) == "a"
    assert functions_in_source(source.read_text(), "lib/a.dart", str(tmp_path))[0].namespace == "a"
