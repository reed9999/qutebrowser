#Tutorial:https://semaphoreci.com/community/tutorials/testing-python-applications-with-pytest 
#See alsohttps://stackoverflow.com/questions/36666225/pyqt5-the-dll-load-failed-the-specified-module-could-not-be-found 
# test_capitalize.py

def capital_case(x):
    return x.capitalize()

def test_capital_case():
    assert capital_case('semaphore') == 'Semaphore'
