import streamlit as st
from streamlit import session_state as session
from gspread_pandas import Spread, Client
from google.oauth2 import service_account
import pyrebase as p
import retrying
import pandas as pd

# SETTING UP GOOGLE SHEET CONNECTION
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']

credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=scope)
client = Client(scope=scope, creds=credentials)
spreadsheetname = "SheetConnection"
spread = Spread(spreadsheetname, client=client)

# Check the connection
# st.write(spread.url)

# SETTING UP FIREBASE CONNECTION
firebaseConfig = {
    'apiKey': "AIzaSyDdsVzOmv12ypmf8NT8j_1MF5YaofwWW0s",
    'authDomain': "sheetconnection-373410.firebaseapp.com",
    'projectId': "sheetconnection-373410",
    'databaseURL': "https://sheetconnection-373410-default-rtdb.europe-west1.firebasedatabase.app",
    'storageBucket': "sheetconnection-373410.appspot.com",
    'messagingSenderId': "653306434623",
    'appId': "1:653306434623:web:a892717e2cb5890a21948a",
    'measurementId': "G-VCV8CQH7SL"
}


def send_verification(users):
    auth.send_email_verification(users['idToken'])
    st.success('Verification link sent to registered email!')


def get_info(key, users):
    return db.child("Users").child(users['localId']).child(key).get().val()


def set_info(key, value, users):
    return db.child("Users").child(users['localId']).child(key).set(value)


def get_real(users, key='emailVerified'):  # 'emailVerified'
    return not auth.get_account_info(users['idToken'])['users'][0][key]


@retrying.retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_sheet(key, spreads=Spread(spreadsheetname, client=client)):
    spreads.open_sheet(key)
    return spreads.sheet_to_df(index=0)


def text_field(label, columns=None, **input_params):
    c1, c2 = st.beta_columns(columns or [1, 4])

    # Display field name with some alignment
    c1.markdown("##")
    c1.markdown(label)

    # Sets a default key parameter to avoid duplicate key errors
    input_params.setdefault("key", label)

    # Forward text input parameters
    return c2.selectbox("", **input_params)


firebase = p.initialize_app(firebaseConfig)
auth = firebase.auth()

db = firebase.database()
storage = firebase.storage()

st.write('user' in session)
if 'user' in session:
    session['verify'] = not auth.get_account_info(session['user']['idToken'])['users'][0]['emailVerified']
home, payments, balances, salary, setting = st.tabs(["Home", "Payments", "Balances", "Salary", "Settings"])

with home:
    if 'user' not in session:
        st.header('Welcome :sunglasses:')
        login, signup = st.tabs(["Login", "Signup"])

        with login:
            if 'user' not in session:
                placeHolder = st.empty()
                with placeHolder.form(key='login', clear_on_submit=False):
                    email = st.text_input("E-mail")
                    password = st.text_input("Password", type="password")
                    btnLogin = st.form_submit_button('Login')

                if btnLogin:
                    if 'user' in session:
                        placeHolder.empty()
                        name = get_info('Name', session['user'])
                        st.header('Hello ' + name + ":wave:")
                        st.write("You are already logged in!")
                    else:
                        try:
                            if email[-4:] == '.com' or email[-3:] == '.in':
                                session['user'] = auth.sign_in_with_email_and_password(email, password)
                                session['verify'] = not auth.get_account_info(session['user']['idToken'])['users'][0]['emailVerified']
                                placeHolder.empty()
                                st.success("Login Successful!")

                                name = get_info('Name', session['user'])
                                st.balloons()
                                st.header('Hello ' + name + ":wave:")
                                st.write(auth.get_account_info(session['user']['idToken']))
                                st.write('user' in session)
                        except Exception as e:
                            print(e)
                            st.error('Invalid Username/Password')
            else:
                name = get_info('Name', session['user'])
                st.header('Hello ' + name + ":wave:")

        with signup:
            if 'user' not in session:
                salarySheet = get_sheet('SalarySheet')  # For getting list for name selection during signup
                placeHolder = st.empty()
                with placeHolder.form(key='signup', clear_on_submit=True):
                    name = st.selectbox("Name", list(salarySheet["Name"]))
                    email = st.text_input("E-mail")
                    col1, col2 = st.columns(2)
                    password = col1.text_input("Create Password", type="password")
                    check = col2.text_input("Repeat Password", type="password")
                    btnSignUp = st.form_submit_button('Sign Up')

                if btnSignUp:
                    if 'user' in session:
                        placeHolder.empty()
                        st.header('Logout to create a new account!')
                    elif password != check:
                        st.error("Password don't match", icon="🚨")
                    else:
                        try:
                            if email[-4:] == '.com' or email[-3:] == '.in':
                                auth.create_user_with_email_and_password(email, password)
                                session['user'] = auth.sign_in_with_email_and_password(email, password)
                                session['verify'] = True

                                placeHolder.empty()
                                st.success('Your account is created successfully')

                                send_verification(session['user'])

                                empid = str(int(salarySheet[salarySheet['Name'] == name]['Empid']))
                                set_info('Name', name, session['user'])
                                set_info('Empid', empid, session['user'])
                                set_info('Id', session['user'], session['user'])
                                role = 'Master' if empid == '1000' else 'Simple'
                                set_info('Role', role, session['user'])

                                st.balloons()
                                st.write("Hello " + str(name) + ":wave:")
                        except Exception as e:
                            print(e)
                            st.error("Error Occurred!")
            else:
                st.header('Logout to create a new account!')
    else:
        name = get_info('Name', session['user'])
        st.header('Welcome ' + name + " :sunglasses:")

with payments:
    if 'user' not in session:
        st.header('Login to access payment records')
    elif session['verify']:
        st.header('Verify email to access payment records')
    else:
        role = get_info('Role', session['user'])
        empid = get_info('Empid', session['user'])
        if role == 'Simple':
            paymentdf = get_sheet('Payments')
            st.header('Your Payment Records')
            st.dataframe(paymentdf.loc[paymentdf['Empid'] == empid])
        elif role == 'Viewer':
            paymentdf = get_sheet('Payments')
            personal, allPayments = st.tabs(['Personal', 'All'])
            with personal:
                st.header('Your Payment Records')
                st.dataframe(paymentdf.loc[paymentdf['Empid'] == empid])
            with allPayments:
                st.header("Payment Records")
                st.dataframe(paymentdf)
        else:
            add, allPayments, personal = st.tabs(['Add', 'All', 'Personal'])
            with add:
                st.header('Add Payment Record')
                entries = []

                dropdown = st.selectbox('Record Method', ['Single', 'Upload Excel'])
                if dropdown == 'Single':
                    # List of names concatenated with id's
                    salarySheet = get_sheet('SalarySheet')
                    new = salarySheet['Name'].astype(str) + " - " + salarySheet['Empid']

                    with st.form(key='addPayment', clear_on_submit=True):
                        name = st.selectbox('Name', list(new))
                        amount = st.text_input('Amount')
                        date = st.date_input('Date')
                        confirm = st.form_submit_button('Confirm')

                    if confirm:
                        paymentdf = get_sheet('Payments')
                        balance = get_sheet('BalanceSheet')

                        oldBalance = int(balance[balance['Empid'] == name[-4:]]["Old Balance (till Mar'22)"])
                        salarySum = int(balance[balance['Empid'] == name[-4:]]["Salary Sum (from Apr'22)"])
                        payedAmount = int(balance[balance['Empid'] == name[-4:]]["Payment Sum (from Apr'22)"])
                        final = oldBalance + salarySum - payedAmount

                        last = len(paymentdf) + 2  # Index where data will be added
                        entry = [name[-4:], date.strftime("%d.%m.%Y"), name[:-7], amount, final, final - int(amount)]
                        spread = Spread(spreadsheetname, client=client)
                        spread.update_cells('A' + str(last), 'F' + str(last), entry)
                        st.success('Updated to Google Sheet')
                else:
                    with st.form('excel', clear_on_submit=True):
                        uploaded_file = st.file_uploader("Choose a file")
                        btnExcel = st.form_submit_button('Upload')

                    if btnExcel:
                        paymentdf = get_sheet('Payments')
                        df = pd.read_excel(uploaded_file)
                        for i in range(len(df)):
                            entries.append(df.iloc[i])

                        last = len(paymentdf) + 2  # Index where data will be added
                        spread = Spread(spreadsheetname, client=client)
                        for i in range(len(entries)):
                            spread.update_cells('A' + str(last + i), 'F' + str(last + i), entries[i])
                        st.success('Updated to Google Sheet')

            with allPayments:
                paymentdf = get_sheet('Payments')
                st.header("Payment Records")
                st.dataframe(paymentdf)
            with personal:
                paymentdf = get_sheet('Payments')
                st.header('Your Payment Records')
                st.dataframe(paymentdf.loc[paymentdf['Empid'] == empid])

with balances:
    if 'user' not in session:
        st.header('Login to access balance records')
    elif session['verify']:
        st.header('Verify email to access balance records')
    else:
        role = get_info('Role', session['user'])
        empid = get_info('Empid', session['user'])
        balance = get_sheet('BalanceSheet')
        if role == 'Simple':
            st.header('Your Balances')
            st.dataframe(balance.loc[balance['Empid'] == empid])
        else:
            personal, allBalance = st.tabs(['Personal', 'All'])
            with personal:
                st.header('Your Balances')
                st.dataframe(balance.loc[balance['Empid'] == empid])
            with allBalance:
                st.header('Balance Sheet')
                st.dataframe(balance)

with salary:
    if 'user' not in session:
        st.header('Login to access salary records')
    elif session['verify']:
        st.header('Verify email to access salary records')
    else:
        role = get_info('Role', session['user'])
        empid = get_info('Empid', session['user'])
        salary = get_sheet('SalarySheet')
        if role == 'Simple':
            st.header('Your Salary Distribution')
            st.dataframe(salary.loc[salary['Empid'] == empid])
        else:
            personal, allBalance = st.tabs(['Personal', 'All'])
            with personal:
                st.header('Your Salary Distribution')
                st.dataframe(salary.loc[salary['Empid'] == empid])
            with allBalance:
                st.header('Salary Sheet')
                st.dataframe(salary)

with setting:
    if 'user' not in session:
        st.header("Login to access settings!")
    elif session['verify']:
        st.header('Verify email to access settings')
    else:
        role = get_info('Role', session['user'])
        salary = get_sheet('SalarySheet')
        if role == 'Master':
            assign, info, logout = st.tabs(['Assign Roles', 'Personal', 'Logout'])
            with assign:
                roles = {}
                with st.form('Assign Roles', clear_on_submit=False):
                    for i in db.child("Users").get().each():
                        opt = ['Simple', 'Viewer', 'Editor', 'Master']
                        roles[i.key()] = st.selectbox(i.val()['Name'], opt, index=opt.index(i.val()['Role']))
                    btnAssign = st.form_submit_button('Assign')
                if btnAssign:
                    for i in db.child("Users").get().each():
                        set_info('Role', roles[i.key()], i.key())
                    st.success("Roles Updated!")
                    st.balloons()
            with info:
                st.header("You are")
                st.write(get_info('Name', session['user']))
                st.write(get_info('Empid', session['user']))
                st.write("Aren't You?")
            with logout:
                st.header("Thank You! Visit Again :ribbon:")
                placeHolder = st.empty()
                btnLogout = placeHolder.button('Logout')
                if btnLogout:
                    placeHolder.empty()
                    currentUser = {}
                    st.success("Logout Successful")
        else:
            info, logout = st.tabs(['Personal', 'Logout'])
            with info:
                st.header("You are")
                st.write(get_info('Name', session['user']))
                st.write(get_info('Empid', session['user']))
                st.write("Aren't You?")
            with logout:
                st.header("Thank You! Visit Again :ribbon:")
                placeHolder = st.empty()
                btnLogout = placeHolder.button('Logout')
                if btnLogout:
                    placeHolder.empty()
                    del session['user']
                    st.success("Logout Successful")
