#!/usr/bin/env python

__author__ = 'Thomas R. Lennan'
__license__ = 'Apache 2.0'

import unittest

from anode.net import entity
from anode.container import cc

from interface.services.ibank_service import IBankService, BaseBankService

#class Test_Bank(unittest.TestCase):
#
#    def test_bank(self):
#        container = cc.Container()
#        container.start() # :(
#
#        client = entity.RPCClientEntityFromInterface(IBankService)
#
#        print "Before start client"
#        container.start_client('bank', client)
#
#        print "Before new account"
#        acctNum = client.new_account('kurt', 'Savings')
#        print "New account number: " + str(acctNum)
#        print "Starting balance %s" % str(client.get_balance(acctNum))
#        client.deposit(acctNum, 99999999)
#        print "Confirming balance after deposit %s" % str(client.get_balance(acctNum))
#        client.withdraw(acctNum, 1000)
#        print "Confirming balance after withdrawl %s" % str(client.get_balance(acctNum))
#        acctList = client.list_accounts('kurt')
#        for acct_obj in acctList:
#            print "Account: " + str(acct_obj)
#
#        container.stop()

#    def test_persistent(self):
#        self.do_test(BankService(persistent=True))

if __name__ == "__main__":
    unittest.main()
    