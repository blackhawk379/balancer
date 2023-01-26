import streamlit as st
from streamlit import session_state as session
from gspread_pandas import Spread, Client
from google.oauth2 import service_account
import pyrebase as p
import retrying
import pandas as pd

# SETTING UP GOOGLE SHEET CONNECTION
scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
credentials = service_account.Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)

@retrying.retry(stop_max_attempt_number=3, wait_fixed=2000)
def connect():
    client1 = Client(scope=scope, creds=credentials)
    return client1

client = connect()
spreadSheetName = "SheetConnection"
spread = Spread(spreadSheetName, client=client)

@retrying.retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_sheet(key, spreads=Spread(spreadSheetName, client=client)):
    spreads.open_sheet(key)
    return spreads.sheet_to_df(index=0)

# SETTING UP FIREBASE CONNECTION
firebase = p.initialize_app(st.secrets['firebaseConfig'])
auth = firebase.auth()
db = firebase.database()
storage = firebase.storage()

def send_verification():
    auth.send_email_verification(session['user']['idToken'])
    st.success('Verification link sent to registered email!')

def get_info():
    fun_name = db.child("Users").child(session['user']['localId']).child('Name').get().val()
    fun_empId = db.child("Users").child(session['user']['localId']).child('EmpId').get().val()
    fun_role = db.child("Users").child(session['user']['localId']).child('Role').get().val()
    fun_id = db.child("Users").child(session['user']['localId']).child('Id').get().val()
    return fun_name, fun_role, fun_empId, fun_id

def set_info():
    db.child("Users").child(session['user']['localId']).child('Name').set(name)
    db.child("Users").child(session['user']['localId']).child('EmpId').set(empId)
    db.child("Users").child(session['user']['localId']).child('Id').set(session['user']['localId'])
    db.child("Users").child(session['user']['localId']).child('Role').set('Master' if empId == '1000' else 'Simple')

def get_real(key='emailVerified'):  # 'emailVerified'
    return not auth.get_account_info(session['user']['idToken'])['users'][0][key]

def update_df(excel_id, excel_amount):
    _index = balanceDf.index[balanceDf['EmpId'] == excel_id].tolist()[0]
    print(balanceDf.iloc[_index])
    final = int(balanceDf.iloc[_index]["Current Balance"])
    payed = int(balanceDf.iloc[_index]["Payment Sum (from Apr'22)"])
    balanceDf.loc[_index, ["Payment Sum (from Apr'22)"]] = payed + int(excel_amount)
    balanceDf.loc[_index, ["Current Balance"]] = final - int(excel_amount)
    return final

def show_info():
    if 'user' in session:
        st.header("You are")
        st.write(name)
        st.write(empId) 
        st.write("Aren't You?")
    else: st.header('You Are Logged Out!')

def show_logout(key):
    st.header("Thank You! Visit Again :ribbon:")
    p1 = st.empty()
    btnOut = p1.button('Logout', key=key)
    if btnOut:
        p1.empty()
        session.pop('user')
        st.success("Logout Successful")
        st.experimental_rerun()

def everything_alright(tab):
    if 'user' not in session: st.header('Login to access ' + tab)
    elif session['verify']: st.header('Verify email to access ' + tab)
    return ('user' in session) and not session['verify']

def hello(): st.header('Hello ' + name + ":wave:")

def no_user():
    if 'user' in session: hello()
    return 'user' not in session

def display_salary():
    st.header('Your Salary and Payment Details')
    st.write(empId + ' - ' + name)
    st.write('Current Balance' + ': ' + str(list(balanceDf.loc[balanceDf['EmpId'] == empId]['Current Balance'])[0]))
    _col1, _col2 = st.columns(2)
    hide_table_row_index = """
                <style>
                thead tr th:first-child {display:none}
                tbody th {display:none}
                </style>
                """
    # Inject CSS with Markdown
    _col1.markdown(hide_table_row_index, unsafe_allow_html=True)
    _index = salaryDf.index[salaryDf['EmpId'] == empId].tolist()[0]
    _title, _data = list(salaryDf.columns), list(salaryDf.iloc[_index])
    _df = pd.DataFrame(list(zip(_title[1:], _data[1:])))
    _df.columns = [_title[0], _data[0]]
    _col1.table(_df)
    _col2.dataframe(paymentDf.loc[paymentDf['EmpId'] == empId])

def display_all(title, sheet, key):
    st.header(title)
    _select = st.selectbox('Select Id:', list(employeeList), label_visibility='collapsed', key=key)
    if _select == 'Select Id': st.dataframe(sheet)
    else: st.dataframe(sheet.loc[sheet['EmpId'] == _select[:4]])

def display(title, sheet):
    st.header(title)
    st.dataframe(sheet.loc[sheet['EmpId'] == empId])

# Getting Information
name, role, empId, Id = "", "", "", ""
if 'user' in session:
    session['verify'] = get_real()
    name, role, empId, Id = get_info()

salarySheet = get_sheet('SalarySheet')
employeeList = list(salarySheet['EmpId'] + " - " + salarySheet['Name'].astype(str))
employeeList.insert(0, 'Select Id')

nonUserList = ['Select Id']
nEmpIdList = salarySheet.loc[salarySheet['Account'] == 'Not Created']['EmpId']
nNameList = salarySheet.loc[salarySheet['Account'] == 'Not Created']['Name']
for i in range(len(nEmpIdList)): nonUserList.append(nEmpIdList[i] + " - " + nNameList[i])
home, payments, balances, salary, setting = st.tabs(["Home", "Payments", "Balances", "Salary", "Settings"])
with home:
    if no_user():
        st.header('Welcome :sunglasses:')
        login, signup = st.tabs(["Login", "Signup"])
        with login:
            if no_user():
                placeHolder = st.empty()
                with placeHolder.form(key='login', clear_on_submit=False):
                    email = st.text_input("E-mail")
                    password = st.text_input("Password", type="password")
                    btnLogin = st.form_submit_button('Login')
                if btnLogin:
                    try:
                        session['user'] = auth.sign_in_with_email_and_password(email, password)
                        session['verify'] = get_real()
                        placeHolder.empty()
                        st.success("Login Successful!")
                        name, role, empId, Id = get_info()
                        st.balloons()
                        hello()
                    except Exception as e:
                        print(e)
                        st.error('Invalid Username/Password')
        with signup:
            if no_user():
                placeHolder = st.empty()
                with placeHolder.form(key='signup', clear_on_submit=True):
                    name = st.selectbox("Name", nonUserList, label_visibility='collapsed')
                    email = st.text_input("E-mail")
                    col1, col2 = st.columns(2)
                    password = col1.text_input("Create Password", type="password")
                    check = col2.text_input("Repeat Password", type="password")
                    btnSignUp = st.form_submit_button('Sign Up')
                if btnSignUp:
                    if password != check: st.error("Password don't match", icon="🚨")
                    elif name == 'Select Id': st.error("Please select your employee details!")
                    else:
                        try:
                            auth.create_user_with_email_and_password(email, password)
                            session['user'] = auth.sign_in_with_email_and_password(email, password)
                            session['verify'] = True
                            placeHolder.empty()
                            st.success('Your account is created successfully')
                            send_verification()
                            empId, name = name[:4], name[7:]
                            index = salarySheet.index[salarySheet['EmpId'] == empId].tolist()[0]
                            spread = Spread(spreadSheetName, client=client)
                            spread.open_sheet(1)
                            spread.update_cells('U' + str(index+2), 'U' + str(index+2), ['Created'])
                            set_info()
                            a, role, b, Id = get_info()
                            st.balloons()
                            hello()
                        except Exception as e:
                            print(e)
                            st.error("Please recheck details")

with payments:
    if everything_alright('payment records'):
        # If 'simple', Display Payment Records of employee
        if role == 'Simple':
            paymentDf = get_sheet('Payments')
            display('Your Payment Records', paymentDf)
            
        # If 'viewer', Display Payment Records of All employee (as well as their own)
        elif role == 'Viewer':
            paymentDf = get_sheet('Payments')
            personal, allPayments = st.tabs(['Personal', 'All'])
            with personal: display('Your Payment Records', paymentDf)
            with allPayments: display_all("Payment Records", paymentDf, 'vap')

        # Else, Give Option to Add Payment Record
        else:
            add, allPayments, personal = st.tabs(['Add', 'All', 'Personal'])
            with add:
                st.header('Add Payment Record')
                # List to store records to be added
                entries = []
                # Last filled index of sheet where new records to be added
                session['last'] = len(get_sheet('Payments')) + 2
                # Loading Sheet to get old balances
                balanceDf = get_sheet('BalanceSheet')
                spread = Spread(spreadSheetName, client=client)
                single, upload = st.tabs(['Single', 'Upload Excel'])
                with single:
                    with st.form(key='addPayment', clear_on_submit=True):
                        _name = st.selectbox('Name', list(employeeList))
                        amount = st.text_input('Amount')
                        date = st.date_input('Date')
                        confirm = st.form_submit_button('Confirm')
                    if confirm:
                        if _name == 'Select Id': st.error("Please select an employee!")
                        else:
                            # Dataframe
                            prev = update_df(name[-4:], int(amount))
                            # Entry Array
                            entry = [name[-4:], date.strftime("%d.%m.%Y"), name[:-7], amount, prev, prev - int(amount)]
                            # Adding Entry to Google Sheet
                            spread.update_cells('A' + str(session['last']), 'F' + str(session['last']), entry)
                            session['last'] += 1
                            st.success('Updated to Google Sheet')
                with upload:
                    with st.form('excel', clear_on_submit=True):
                        uploaded_file = st.file_uploader("Choose a file")
                        btnExcel = st.form_submit_button('Upload')
                    if btnExcel:
                        df = pd.read_excel(uploaded_file)
                        size = len(df)
                        for i in range(size):
                            entries.extend(list(df.iloc[i]))
                            name, amount = str(entries[6 * i + 0]), entries[6 * i + 3]
                            prev = update_df(name, amount)
                            entries.extend([prev, prev - amount])
                        for i in range(len(entries)): entries[i] = str(entries[i])
                        spread.update_cells('A' + str(session['last']), 'F' + str(session['last'] + size - 1), entries)
                        st.success('Updated to Google Sheet')
                        st.snow()
            with allPayments:
                paymentDf = get_sheet('Payments')
                display_all("Payment Records", paymentDf, 'eap')
            with personal:
                paymentDf = get_sheet('Payments')
                display('Your Payment Records', paymentDf)

with balances:
    if everything_alright('balance sheet'):
        balanceDf = get_sheet('BalanceSheet')
        if role == 'Simple': display('Your Balances', balanceDf)
        else:
            personal, allBalance = st.tabs(['Personal', 'All'])
            with personal: display('Your Balances', balanceDf)
            with allBalance: display_all('Balance Sheet', balanceDf, 'ab')

with salary:
    if everything_alright('salary and payment details'):
        salaryDf = get_sheet('SalarySheet'), get_sheet('BalanceSheet'), get_sheet('Payments')
        if role == 'Simple': display_salary()
        else:
            personal, allSalary = st.tabs(['Personal', 'All'])
            with personal: display_salary()
            with allSalary: display_all('Salary Sheet', salaryDf, 'as')

with setting:
    if everything_alright("Settings"):
        if role == 'Master':
            assign, info, logout = st.tabs(['Assign Roles', 'Personal', 'Logout'])
            with assign:
                roles = {}  # Initializing dictionary for taking role input
                try:
                    with st.form('Assign Roles', clear_on_submit=False):
                        for i in db.child("Users").get().each():  # Iterating through session['user']
                            uName, uRole = i.val()['Name'], i.val()['Role']  # Getting Name and EmpId of a user
                            opt = ['Simple', 'Viewer', 'Editor', 'Master']  # Getting available Roles
                            opt = [uName + ' - ' + j for j in opt]  # Concatenating Name with Role
                            roles[i.key()] = st.selectbox(uName, opt, index=opt.index(uName + '-' + uRole), label_visibility='collapsed')  # Getting input
                        btnAssign = st.form_submit_button('Assign')
                        if btnAssign:
                            for i in db.child("Users").get().each():
                                db.child("Users").child(i.key()).child('Role').set(roles[i.key()][-6:])
                            st.success("Roles Updated!")
                            st.balloons()
                except Exception as e: print(e)
            with info: show_info()
            with logout: show_logout(1)
        else:
            info, logout = st.tabs(['Personal', 'Logout'])
            with info: show_info()
            with logout: show_logout(2)
