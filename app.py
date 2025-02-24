import streamlit as st
import pandas as pd
import smtplib
import os
import csv
import uuid
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email_validator import validate_email, EmailNotValidError
from streamlit_quill import st_quill  # Editor rico para formatação

# Arquivo de log para registrar os envios
LOG_FILE = "email_log.csv"

# Inicializa o arquivo de log, se não existir
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "email", "domain", "status", "error_message", "tracking_id"])

def log_email_event(email, status, error_message, tracking_id):
    timestamp = datetime.now().isoformat()
    domain = email.split("@")[-1] if "@" in email else ""
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, email, domain, status, error_message, tracking_id])

# Função para enviar e-mail via SMTP com SSL, incluindo anexos e tracking pixel
def send_email(smtp_server, smtp_port, email_user, email_password, to_email, subject, body, attachments=None):
    # Gera uma ID única para rastreamento
    tracking_id = str(uuid.uuid4())
    # Cria um pixel de rastreamento (substitua a URL pelo seu endpoint real)
    tracking_pixel = f'<img src="https://yourserver.com/tracker?email={to_email}&id={tracking_id}" alt="" style="display:none;">'
    
    # Se o corpo não contiver tags HTML, converte quebras de linha para <br>
    if "<" not in body:
        formatted_body = body.replace("\n", "<br>")
    else:
        formatted_body = body

    # Cria um template HTML para preservar a formatação
    html_body = f"""
    <html>
      <head>
        <meta charset="utf-8">
        <style>
          body {{
            font-family: Arial, sans-serif;
            white-space: pre-wrap;
          }}
        </style>
      </head>
      <body>
        {formatted_body}
        {tracking_pixel}
      </body>
    </html>
    """
    
    msg = MIMEMultipart()
    msg['From'] = email_user
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    
    if attachments:
        for attachment in attachments:
            try:
                part = MIMEApplication(attachment.getvalue(), Name=attachment.name)
                part['Content-Disposition'] = f'attachment; filename="{attachment.name}"'
                msg.attach(part)
            except Exception as e:
                st.error(f"Erro ao anexar {attachment.name}: {e}")
    
    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(email_user, email_password)
        server.sendmail(email_user, to_email, msg.as_string())
        server.quit()
        log_email_event(to_email, "success", "", tracking_id)
        return True, "Enviado com sucesso"
    except Exception as e:
        log_email_event(to_email, "error", str(e), tracking_id)
        return False, str(e)

# ─── Sidebar: Configurações do SMTP ───────────────────────────────
st.sidebar.title("Configurações do SMTP")
smtp_server = st.sidebar.text_input("Servidor SMTP", "smtp.hostinger.com")
smtp_port = st.sidebar.number_input("Porta", value=465)
email_user = st.sidebar.text_input("Email", "comercial@rodoveigatransportes.com.br")
email_password = st.sidebar.text_input("Senha", type="password", value="")

# ─── Título e Método de Envio ───────────────────────────────
st.title("Sistema de Envio de Emails em Massa")
method = st.radio("Escolha o método de envio:", ("Email Único", "Lista de Emails via Upload"))

# ─── Configuração do E-mail ───────────────────────────────
subject = st.text_input("Assunto", "Cadastro Rodoveiga Transportes")
st.markdown("### Corpo do Email")
body = st_quill("Digite o corpo do email com formatação, emojis, etc.")

# ─── Seleção de Destinatários ───────────────────────────────
if method == "Email Único":
    single_email = st.text_input("Digite o email do destinatário")
    emails_to_send = [single_email] if single_email else []
else:
    uploaded_file = st.file_uploader("Faça o upload do arquivo CSV ou Excel com a lista de emails", type=["csv", "xlsx"])
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith("csv"):
                df = pd.read_csv(uploaded_file, header=None)
            else:
                df = pd.read_excel(uploaded_file, header=None)
            # Assume que os emails estão na primeira coluna (coluna A)
            emails_to_send = df.iloc[:, 0].tolist()
            st.write("Emails lidos do arquivo:")
            st.write(emails_to_send)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
            emails_to_send = []
    else:
        emails_to_send = []

# ─── Upload de Anexos (opcional) ───────────────────────────────
attachments = st.file_uploader("Anexos (arquivos para enviar com o email)", 
                               type=["pdf", "docx", "png", "jpg", "jpeg", "xlsx", "csv", "txt"], 
                               accept_multiple_files=True)

# ─── Botão para Enviar os E-mails ───────────────────────────────
if st.button("Enviar Email"):
    if not email_user or not email_password:
        st.error("Configure as credenciais do SMTP na barra lateral!")
    elif not emails_to_send:
        st.error("Nenhum email para enviar!")
    else:
        results = []
        progress_bar = st.progress(0)
        total = len(emails_to_send)
        for i, email in enumerate(emails_to_send):
            try:
                validate_email(email)
            except EmailNotValidError as e:
                results.append((email, f"Email inválido: {e}"))
                continue

            success, message = send_email(smtp_server, smtp_port, email_user, email_password, email, subject, body, attachments)
            results.append((email, message))
            progress_bar.progress((i+1)/total)
        st.write("### Relatório de Envio")
        st.table(results)

# ─── Relatório de Envios (Logs) ───────────────────────────────
st.markdown("### Relatório de Emails Enviados")

# Campo para inserir palavras-chave para excluir emails (ex: "exemplo, teste")
exclude_keywords = st.text_input("Excluir emails que contenham (palavras separadas por vírgula)", "exemplo, teste")

if st.button("Gerar Relatório"):
    if os.path.exists(LOG_FILE):
        log_df = pd.read_csv(LOG_FILE)
        # Converter timestamp para datetime
        log_df['timestamp'] = pd.to_datetime(log_df['timestamp'])
        # Adicionar colunas para dia, semana, mês e ano
        log_df['dia'] = log_df['timestamp'].dt.date
        log_df['semana'] = log_df['timestamp'].dt.to_period('W').apply(lambda r: r.start_time)
        log_df['mes'] = log_df['timestamp'].dt.to_period('M').apply(lambda r: r.start_time)
        log_df['ano'] = log_df['timestamp'].dt.year
        
        # Se o usuário informou palavras-chave para excluir, aplica o filtro
        if exclude_keywords:
            keywords = [kw.strip() for kw in exclude_keywords.split(",") if kw.strip()]
            for kw in keywords:
                log_df = log_df[~log_df['email'].str.contains(kw, case=False, na=False)]
        
        st.write("Relatório Geral:")
        st.dataframe(log_df)
        
        # Relatório por domínio
        log_df['domain'] = log_df['email'].apply(lambda x: x.split('@')[-1] if pd.notnull(x) else "")
        domain_report = log_df.groupby('domain').agg(
            total_emails=('email', 'count'),
            sucesso=('status', lambda x: (x == "success").sum()),
            erros=('status', lambda x: (x == "error").sum())
        ).reset_index()
        st.write("Relatório por Domínio:")
        st.dataframe(domain_report)
    else:
        st.error("Nenhum log de envio encontrado.")

