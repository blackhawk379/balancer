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


@retrying.retry(stop_max_attempt_number=3, wait_fixed=2000)
def connect():
    client1 = Client(scope=scope, creds=credentials)
    return client1


client = connect()

spreadsheetname = "SheetConnection"
spread = Spread(spreadsheetname, client=client)

# Check the connection
# st.write(spread.url)


@retrying.retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_sheet(key, spreads=Spread(spreadsheetname, client=client)):
    spreads.open_sheet(key)
    return spreads.sheet_to_df(index=0)


# SETTING UP FIREBASE CONNECTION
firebase = p.initialize_app(st.secrets['firebaseConfig'])
auth = firebase.auth()

db = firebase.database()
storage = firebase.storage()


def send_verification(users):
    auth.send_email_verification(users['idToken'])
    st.success('Verification link sent to registered email!')


def get_info(key, users):
    return db.child("Users").child(users['localId']).child(key).get().val()


def set_info(key, value, users):
    return db.child("Users").child(users['localId']).child(key).set(value)


def get_real(users, key='emailVerified'):  # 'emailVerified'
    return not auth.get_account_info(users['idToken'])['users'][0][key]


def update_df(excel_id, excel_amount, dataframe):
    index = dataframe.index[dataframe['Empid'] == excel_id].tolist()[0]
    print(dataframe.iloc[index])
    final = int(dataframe.iloc[index]["Current Balance"])
    payed = int(dataframe.iloc[index]["Payment Sum (from Apr'22)"])
    dataframe.loc[index, ["Payment Sum (from Apr'22)"]] = payed + int(excel_amount)
    dataframe.loc[index, ["Current Balance"]] = final - int(excel_amount)
    return final


if 'user' in session:
    session['verify'] = not auth.get_account_info(session['user']['idToken'])['users'][0][
        'emailVerified']
    
home, payments, balances, salary, setting = st.tabs(["Home", "Payments", "Balances", "Salary", "Settings"])

with home:
    if 'user' in session:
        name = get_info('Name', session['user'])
        st.header('Welcome ' + name + " :sunglasses:")
    else:
        st.header('Welcome :sunglasses:')
        login, signup = st.tabs(["Login", "Signup"])

        with login:
            if 'user' in session:
                name = get_info('Name', session['user'])
                st.header('Hello ' + name + ":wave:")
            else:
                placeHolder = st.empty()
                with placeHolder.form(key='login', clear_on_submit=False):
                    email = st.text_input("E-mail")
                    password = st.text_input("Password", type="password")
                    btnLogin = st.form_submit_button('Login')

                if btnLogin:
                    try:
                        session['user'] = auth.sign_in_with_email_and_password(email, password)
                        session['verify'] = not auth.get_account_info(session['user']['idToken'])['users'][0]['emailVerified']
                        placeHolder.empty()
                        st.success("Login Successful!")

                        name = get_info('Name', session['user'])
                        st.balloons()
                        st.header('Hello ' + name + ":wave:")
                    except Exception as e:
                        print(e)
                        st.error('Invalid Username/Password')

        with signup:
            if 'user' in session:
                st.header('Logout to create a new account!')
            else:
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
                    if password != check:
                        st.error("Password don't match", icon="🚨")
                    else:
                        try:
                            auth.create_user_with_email_and_password(email, password)
                            session['user'] = auth.sign_in_with_email_and_password(email, password)
                            session['verify'] = True

                            placeHolder.empty()
                            st.success('Your account is created successfully')

                            send_verification(session['user'])

                            empid = str(int(salarySheet[salarySheet['Name'] == name]['Empid']))
                            set_info('Name', name, session['user'])
                            set_info('Empid', empid, session['user'])
                            set_info('Id', session['user'], session['user']['localId'])
                            role = 'Master' if empid == '1000' else 'Simple'
                            set_info('Role', role, session['user'])

                            st.balloons()
                            st.write("Hello " + str(name) + ":wave:")
                        except Exception as e:
                            print(e)
                            st.error("Please recheck details")

with payments:
    if 'user' not in session:
        st.header('Login to access payment records')
    elif session['verify']:
        st.header('Verify email to access payment records')
    else:
        role = get_info('Role', session['user'])
        empid = get_info('Empid', session['user'])

        # If 'simple', Display Payment Records of employee
        if role == 'Simple':
            paymentdf = get_sheet('Payments')
            st.header('Your Payment Records')
            st.dataframe(paymentdf.loc[paymentdf['Empid'] == empid])

        # If 'viewer', Display Payment Records of All employee (as well as their own)
        elif role == 'Viewer':
            paymentdf = get_sheet('Payments')
            personal, allPayments = st.tabs(['Personal', 'All'])
            with personal:
                st.header('Your Payment Records')
                st.dataframe(paymentdf.loc[paymentdf['Empid'] == empid])
            with allPayments:
                st.header("Payment Records")
                salarySheet = get_sheet('SalarySheet')
                new = list(salarySheet['Name'].astype(str) + " - " + salarySheet['Empid'])
                new.insert(0, 'Select Id')

                select = st.selectbox('Select Id:', list(new), label_visibility='collapsed', key = 1)
                if select == 'Select Id':
                    st.dataframe(paymentdf)
                else:
                    st.dataframe(paymentdf.loc[paymentdf['Empid'] == select[-4:]])

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

                # List of names concatenated with id's
                salarySheet = get_sheet('SalarySheet')
                new = salarySheet['Name'].astype(str) + " - " + salarySheet['Empid']

                single, upload = st.tabs(['Single', 'Upload Excel'])
                with single:
                    with st.form(key='addPayment', clear_on_submit=True):
                        name = st.selectbox('Name', list(new))
                        amount = st.text_input('Amount')
                        date = st.date_input('Date')
                        confirm = st.form_submit_button('Confirm')

                    if confirm:
                        # Dataframe
                        prev = update_df(name[-4:], int(amount), balanceDf)

                        # Entry Array
                        entry = [name[-4:], date.strftime("%d.%m.%Y"), name[:-7], amount, prev, prev - int(amount)]

                        # Adding Entry to Google Sheet
                        spread = Spread(spreadsheetname, client=client)
                        spread.update_cells('A' + str(session['last']), 'F' + str(session['last']), entry)
                        session['last'] += 1
                        st.success('Updated to Google Sheet')
                with upload:
                    with st.form('excel', clear_on_submit=True):
                        uploaded_file = st.file_uploader("Choose a file")
                        btnExcel = st.form_submit_button('Upload')

                    if btnExcel:
                        df = pd.read_excel(uploaded_file)
                        maxx = len(df)

                        for i in range(maxx):
                            entries.extend(list(df.iloc[i]))
                            name, amount = str(entries[6*i + 0]), entries[6*i + 3]
                            prev = update_df(name, amount, balanceDf)
                            entries.extend([prev, prev - amount])

                        for i in range(len(entries)):
                            entries[i] = str(entries[i])
                        spread = Spread(spreadsheetname, client=client)
                        spread.update_cells('A' + str(session['last']), 'F' + str(session['last'] + maxx - 1), entries)

                        st.success('Updated to Google Sheet')
                        st.snow()

            with allPayments:
                st.header("Payment Records")
                paymentdf = get_sheet('Payments')
                salarySheet = get_sheet('SalarySheet')
                new = list(salarySheet['Name'].astype(str) + " - " + salarySheet['Empid'])
                new.insert(0, 'Select Id')
                select = st.selectbox('Select Id:', list(new), label_visibility='collapsed', key = 2)

                if select == 'Select Id':
                    st.dataframe(paymentdf)
                else:
                    st.dataframe(paymentdf.loc[paymentdf['Empid'] == select[-4:]])
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
                st.header("Balance Sheet")
                salarySheet = get_sheet('SalarySheet')
                new = list(salarySheet['Name'].astype(str) + " - " + salarySheet['Empid'])
                new.insert(0, 'Select Id')

                select = st.selectbox('Select Id:', list(new), label_visibility='collapsed', key = 3)
                if select == 'Select Id':
                    st.dataframe(balance)
                else:
                    st.dataframe(balance.loc[balance['Empid'] == select[-4:]])

with salary:
    if 'user' not in session:
        st.header('Login to access salary records')
    elif session['verify']:
        st.header('Verify email to access salary records')
    else:
        role = get_info('Role', session['user'])
        empid = get_info('Empid', session['user'])
        salary = get_sheet('SalarySheet')
        paymentdf = get_sheet('Payments')
        if role == 'Simple':
            st.header('Your Salary Distribution')
            col1, col2 = st.columns(2)
            index = salary.index[salary['Empid'] == empid].tolist()[0]
            col1.dataframe(pd.DataFrame(list(zip(list(salary.columns), list(salary.iloc[index])))))
            col2.dataframe(paymentdf.loc[paymentdf['Empid'] == empid])
        else:
            personal, allBalance = st.tabs(['Personal', 'All'])
            with personal:
                st.header('Your Salary Distribution')
                col11, col21 = st.columns(2)
                index = salary.index[salary['Empid'] == empid].tolist()[0]
                col11.dataframe(pd.DataFrame(list(zip(list(salary.columns), list(salary.iloc[index])))))
                col21.dataframe(paymentdf.loc[paymentdf['Empid'] == empid])
            with allBalance:
                st.header("Salary Sheet")
                salarySheet = get_sheet('SalarySheet')
                new = list(salarySheet['Name'].astype(str) + " - " + salarySheet['Empid'])
                new.insert(0, 'Select Id')
                select = st.selectbox('Select Id:', list(new), label_visibility='collapsed', key = 4)
                if select == 'Select Id':
                    st.dataframe(salary)
                else:
                    index = salary.index[salary['Empid'] == select].tolist()[0]
                    st.dataframe(pd.DataFrame(list(zip(list(salary.columns), list(salary.iloc[index])))))

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
                        for j in range(4):
                            if opt[j] == i.val()['Role']:
                                assign_role = opt[j]
                                opt.insert(0, i.val()['Name']+' ('+assign_role+')')
                                opt.remove(assign_role)

                        roles[i.key()] = st.selectbox(i.val()['Name'], opt, label_visibility='collapsed')
                    btnAssign = st.form_submit_button('Assign')
                if btnAssign:
                    for i in db.child("Users").get().each():
                        db.child("Users").child(i.key()).child('Role').set(roles[i.key()])
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
                    session.pop('user')
                    st.success("Logout Successful")
                    st.experimental_rerun()
        else:
            info, logout = st.tabs(['Personal', 'Logout'])
            with info:
                if 'user' in session:
                    st.header("You are")
                    st.write(get_info('Name', session['user']))
                    st.write(get_info('Empid', session['user']))
                    st.write("Aren't You?")
                else:
                    st.header('You Are Logged Out!')
            with logout:
                st.header("Thank You! Visit Again :ribbon:")
                placeHolder = st.empty()
                btnLogout = placeHolder.button('Logout')
                if btnLogout:
                    placeHolder.empty()
                    session.pop('user')
                    st.success("Logout Successful")
                    st.experimental_rerun()
