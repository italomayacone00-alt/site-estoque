import csv
import io
import os  # <--- Essencial para ler configurações do Render
import xml.etree.ElementTree as ET
from flask import Flask, render_template, request, redirect, url_for, Response, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)

# ==========================================
# 🔐 SEGURANÇA E CONFIGURAÇÃO (RENDER)
# ==========================================

# 1. SECRET_KEY
# Tenta pegar a senha segura do Render. Se não achar (no seu PC), usa a 'chave_dev'.
app.secret_key = os.environ.get('SECRET_KEY', 'chave_desenvolvimento_local_segura')

# 2. BANCO DE DADOS
# Tenta pegar o banco do Render (PostgreSQL). Se não achar, usa o SQLite local.
database_url = os.environ.get('DATABASE_URL')

# O Render fornece URL como 'postgres://', mas o SQLAlchemy precisa de 'postgresql://'
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///estoque.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- CONFIGURAÇÃO DE LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==========================================
# MODELOS (TABELAS)
# ==========================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    preco = db.Column(db.Float, nullable=False)
    preco_compra = db.Column(db.Float, nullable=True)
    validade = db.Column(db.String(20), nullable=True)

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    cidade = db.Column(db.String(50), nullable=True)

class Venda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.now)
    quantidade = db.Column(db.Integer, nullable=False)
    valor_total = db.Column(db.Float, nullable=False)
    
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=True)
    
    produto = db.relationship('Produto')
    cliente = db.relationship('Cliente')

# Cria tabelas (Importante: No Render, isso roda ao iniciar)
with app.app_context():
    db.create_all()

# ==========================================
# ROTAS DE AUTENTICAÇÃO
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha incorretos.', 'danger')
            
    return render_template('login.html')

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Usuário já existe.', 'danger')
            return redirect(url_for('registrar'))
        
        novo_user = User(username=username)
        novo_user.set_password(password)
        db.session.add(novo_user)
        db.session.commit()
        
        flash('Conta criada! Faça login.', 'success')
        return redirect(url_for('login'))
        
    return render_template('registrar.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Saiu com sucesso.', 'info')
    return redirect(url_for('login'))

# ==========================================
# ROTAS DO SISTEMA (ESTOQUE)
# ==========================================

@app.route('/')
@login_required
def index():
    produtos = Produto.query.all()
    return render_template('index.html', produtos=produtos, pagina_atual='estoque')

@app.route('/adicionar', methods=['GET', 'POST'])
@login_required
def adicionar():
    if request.method == 'POST':
        p_compra = request.form.get('preco_compra')
        p_compra = float(p_compra) if p_compra else None
        
        novo_produto = Produto(
            nome=request.form['nome'], 
            quantidade=int(request.form['quantidade']), 
            preco=float(request.form['preco']),
            preco_compra=p_compra,
            validade=request.form.get('validade')
        )
        db.session.add(novo_produto)
        db.session.commit()
        flash('Produto adicionado!', 'success')
        return redirect(url_for('index'))
    return render_template('adicionar.html', pagina_atual='estoque')

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    produto = Produto.query.get_or_404(id)
    if request.method == 'POST':
        produto.nome = request.form['nome']
        produto.quantidade = int(request.form['quantidade'])
        produto.preco = float(request.form['preco'])
        p_compra = request.form.get('preco_compra')
        produto.preco_compra = float(p_compra) if p_compra else None
        produto.validade = request.form.get('validade')
        db.session.commit()
        flash('Atualizado!', 'success')
        return redirect(url_for('index'))
    return render_template('adicionar.html', produto=produto, pagina_atual='estoque')

@app.route('/deletar/<int:id>')
@login_required
def deletar(id):
    produto = Produto.query.get_or_404(id)
    db.session.delete(produto)
    db.session.commit()
    flash('Removido.', 'success')
    return redirect(url_for('index'))

# --- CLIENTES ---
@app.route('/clientes')
@login_required
def clientes():
    lista_clientes = Cliente.query.all()
    return render_template('clientes.html', clientes=lista_clientes, pagina_atual='clientes')

@app.route('/clientes/adicionar', methods=['GET', 'POST'])
@login_required
def adicionar_cliente():
    if request.method == 'POST':
        novo_cliente = Cliente(
            nome=request.form['nome'], telefone=request.form.get('telefone'),
            email=request.form.get('email'), cidade=request.form.get('cidade')
        )
        db.session.add(novo_cliente)
        db.session.commit()
        flash('Cliente cadastrado!', 'success')
        return redirect(url_for('clientes'))
    return render_template('adicionar_cliente.html', pagina_atual='clientes')

@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        cliente.nome = request.form['nome']
        cliente.telefone = request.form.get('telefone')
        cliente.email = request.form.get('email')
        cliente.cidade = request.form.get('cidade')
        db.session.commit()
        flash('Cliente atualizado!', 'success')
        return redirect(url_for('clientes'))
    return render_template('adicionar_cliente.html', cliente=cliente, pagina_atual='clientes')

@app.route('/clientes/deletar/<int:id>')
@login_required
def deletar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    db.session.delete(cliente)
    db.session.commit()
    flash('Cliente removido.', 'success')
    return redirect(url_for('clientes'))

# --- VENDAS ---
@app.route('/vendas')
@login_required
def vendas():
    lista_vendas = Venda.query.order_by(Venda.data.desc()).all()
    return render_template('vendas.html', vendas=lista_vendas, pagina_atual='vendas')

@app.route('/vendas/nova', methods=['GET', 'POST'])
@login_required
def nova_venda():
    if request.method == 'POST':
        produto_id = int(request.form['produto_id'])
        cliente_id_form = request.form.get('cliente_id')
        quantidade = int(request.form['quantidade'])
        produto = Produto.query.get(produto_id)
        
        if produto.quantidade < quantidade:
            flash(f'Estoque insuficiente! Restam {produto.quantidade}.', 'danger')
            return redirect(url_for('nova_venda'))

        valor_total = produto.preco * quantidade
        nova_venda = Venda(
            produto_id=produto_id, cliente_id=int(cliente_id_form) if cliente_id_form else None,
            quantidade=quantidade, valor_total=valor_total
        )
        produto.quantidade -= quantidade
        db.session.add(nova_venda)
        db.session.commit()
        flash('Venda registrada!', 'success')
        return redirect(url_for('vendas'))
        
    produtos = Produto.query.all()
    clientes = Cliente.query.all()
    return render_template('nova_venda.html', produtos=produtos, clientes=clientes, pagina_atual='vendas')

# --- RELATÓRIOS ---
@app.route('/relatorios')
@login_required
def relatorios():
    produtos = Produto.query.all()
    vendas = Venda.query.all()
    
    total_faturamento = sum(v.valor_total for v in vendas)
    total_itens_vendidos = sum(v.quantidade for v in vendas)
    valor_estoque_custo = sum((p.preco_compra or 0) * p.quantidade for p in produtos)
    valor_estoque_venda = sum(p.preco * p.quantidade for p in produtos)
    lucro_estimado_estoque = valor_estoque_venda - valor_estoque_custo
    
    vendas_por_produto = {}
    for v in vendas:
        if v.produto: 
            vendas_por_produto[v.produto.nome] = vendas_por_produto.get(v.produto.nome, 0) + v.quantidade
    grafico_prod_labels = list(vendas_por_produto.keys())
    grafico_prod_values = list(vendas_por_produto.values())

    faturamento_diario = {}
    for v in vendas:
        dt = v.data.strftime('%d/%m')
        faturamento_diario[dt] = faturamento_diario.get(dt, 0) + v.valor_total
    grafico_dia_labels = list(faturamento_diario.keys())
    grafico_dia_values = list(faturamento_diario.values())
    
    estoque_baixo = [p for p in produtos if p.quantidade < 5]
    
    return render_template('relatorios.html', pagina_atual='relatorios', total_faturamento=total_faturamento, total_itens_vendidos=total_itens_vendidos, valor_estoque_custo=valor_estoque_custo, valor_estoque_venda=valor_estoque_venda, lucro_estimado=lucro_estimado_estoque, grafico_prod_labels=grafico_prod_labels, grafico_prod_values=grafico_prod_values, grafico_dia_labels=grafico_dia_labels, grafico_dia_values=grafico_dia_values, estoque_baixo=estoque_baixo)

# --- GERENCIAMENTO (CSV & MODELOS) ---
@app.route('/gerenciamento')
@login_required
def gerenciamento():
    return render_template('gerenciamento.html', pagina_atual='gerenciamento')

@app.route('/baixar_modelo')
@login_required
def baixar_modelo():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['nome', 'quantidade', 'preco_venda', 'preco_custo', 'validade'])
    writer.writerow(['Exemplo Camiseta', '10', '50.00', '25.00', ''])
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=modelo_estoque.csv"})

@app.route('/importar_csv', methods=['POST'])
@login_required
def importar_csv():
    if 'arquivo_csv' not in request.files:
        flash('Nenhum arquivo.', 'danger')
        return redirect(url_for('gerenciamento'))
    arquivo = request.files['arquivo_csv']
    if arquivo.filename == '':
        flash('Selecione um arquivo.', 'danger')
        return redirect(url_for('gerenciamento'))
    try:
        stream = io.StringIO(arquivo.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.reader(stream)
        next(csv_input, None) 
        count_novos = 0
        count_at = 0
        for row in csv_input:
            if not row or len(row) < 3: continue
            try:
                nome = row[0].strip()
                if not nome: continue
                qtd = int(row[1])
                preco_venda = float(row[2].replace(',', '.'))
                preco_custo = float(row[3].replace(',', '.')) if len(row)>3 and row[3] else 0.0
                validade = row[4].strip() if len(row)>4 else ""
                
                prod = Produto.query.filter_by(nome=nome).first()
                if prod:
                    prod.quantidade += qtd
                    if preco_custo > 0: prod.preco_compra = preco_custo
                    count_at += 1
                else:
                    db.session.add(Produto(nome=nome, quantidade=qtd, preco=preco_venda, preco_compra=preco_custo, validade=validade))
                    count_novos += 1
            except ValueError: continue
        db.session.commit()
        flash(f'Importação: {count_novos} novos, {count_at} atualizados.', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Erro: {str(e)}', 'danger')
        return redirect(url_for('gerenciamento'))

@app.route('/exportar/<tipo>')
@login_required
def exportar(tipo):
    output = io.StringIO()
    writer = csv.writer(output)
    filename = "dados.csv"
    if tipo == 'produtos':
        filename = "produtos.csv"
        writer.writerow(['ID', 'Nome', 'Quantidade', 'Preço Venda', 'Preço Custo'])
        for i in Produto.query.all(): writer.writerow([i.id, i.nome, i.quantidade, i.preco, i.preco_compra])
    elif tipo == 'vendas':
        filename = "vendas.csv"
        writer.writerow(['ID', 'Data', 'Produto', 'Cliente', 'Qtd', 'Total'])
        for i in Venda.query.all():
            p_nome = i.produto.nome if i.produto else "Removido"
            c_nome = i.cliente.nome if i.cliente else 'Balcão'
            writer.writerow([i.id, i.data, p_nome, c_nome, i.quantidade, i.valor_total])
    elif tipo == 'clientes':
        filename = "clientes.csv"
        writer.writerow(['ID', 'Nome', 'Telefone', 'Email', 'Cidade'])
        for i in Cliente.query.all(): writer.writerow([i.id, i.nome, i.telefone, i.email, i.cidade])
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename={filename}"})

@app.route('/limpar_vendas')
@login_required
def limpar_vendas():
    try:
        db.session.query(Venda).delete()
        db.session.commit()
        flash('Histórico limpo.', 'success')
        return redirect(url_for('gerenciamento'))
    except:
        db.session.rollback()
        flash('Erro.', 'danger')
        return redirect(url_for('gerenciamento'))

# Cache Busting para atualizar CSS no navegador
@app.url_defaults
def hashed_url_for_static_file(endpoint, values):
    if 'static' == endpoint or endpoint.endswith('.static'):
        filename = values.get('filename')
        if filename:
            static_folder = app.static_folder
            file_path = os.path.join(static_folder, filename)
            if os.path.exists(file_path):
                values['v'] = int(os.stat(file_path).st_mtime)

if __name__ == "__main__":
    app.run(debug=True)