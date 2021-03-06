
import web3
import time
from datetime import datetime
import sorting
import json
import pandas as pd
import numpy as np
from datetime import datetime
import pprint

from web3 import Web3, IPCProvider, HTTPProvider

#Connection to BC
web3 = Web3(HTTPProvider("http://localhost:8501"))
Flexmarket_address = web3.toChecksumAddress("0x3c375af1aac69f7af48b19ad06231f6633251b2e")

with open("ABI.json") as f:
    abi = json.load(f)

Flexmarket_contract = web3.eth.contract(abi = abi, address = Flexmarket_address)


#Settings for Dataframe
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)
pd.options.display.float_format = '{:.0f}'.format

#Info for the Timer
markettime = 15 #value in minutes
noOfTimesteps = 1440/markettime #96
dt = datetime.now()
timestep = int((dt.hour * 3600 + dt.minute *60 + dt.second)/(markettime*60))

while True:
    time.sleep(1)
    dt = datetime.now()
    print('Working!')
    '''if((dt.hour * 3600 + dt.minute *60 + dt.second)%(markettime*60) == 0):
        if(timestep < noOfTimesteps-1):
            timestep = timestep +1
        else:
            timestep = 0'''


    start_timersim = time.time() #Timer fot the Simulation

    print(f'Results of current timestep: {timestep} are being copied')
    web3.parity.personal.unlockAccount(web3.eth.accounts[3], "Ukulele112", None)
    Flexmarket_contract.functions.copyResult(timestep).transact({'from': web3.eth.accounts[3]})
    print("Done copying Results!")

    t = timestep + 1  # start with the matching process one step after the current timestep

    for t in range(96):

        print(f'Timestep: {t}\n')

        # Get Demands
        web3.parity.personal.unlockAccount(web3.eth.accounts[3], "Ukulele112", None)
        (flxtp2, pwr2, prc2, engy2) = Flexmarket_contract.functions.getDemandsTime(t).call({'from': web3.eth.accounts[3]})
        web3.parity.personal.unlockAccount(web3.eth.accounts[3], "Ukulele112", None)
        (add2) = Flexmarket_contract.functions.getDemandsOwnerTime(t).call({'from': web3.eth.accounts[3]})

        # Filtering Demands + Sorting Demands
        if all([v == 0 for v in prc2]):
            print(f'Demands List in timestep {t} is empty\n')
            print(f'No matching Results\n')
            continue
        else:
            #Dataframe For Storing Demands
            df_de = pd.DataFrame({'Flextype': np.array(flxtp2),
                                  'Power': np.array(pwr2),
                                  'Price': np.array(prc2),
                                  'Energy': np.array(engy2),
                                  'DemandOwner': np.array(add2)})

            #Create Dictionary
            df_demands_dic = df_de.to_dict()
            print(f'Demands at timestep {t}:\n{df_de}\n')

            #Sorting
            df_de = df_de.sort_values(by=['Price'], kind='quicksort', ascending=False)
            #Filtering
            df_de = df_de[df_de.Energy != 0]

            print(f'Filtered and Sorted Demands in timestep {t}\n')
            print(f'{df_de}\n')

            # Contract to push Demands into Sortedemands in BC
            # Really necessary?

        # Get Offers
        web3.parity.personal.unlockAccount(web3.eth.accounts[3], "Ukulele112", None)
        (flxtp1, pwr1, prc1, engy1) = Flexmarket_contract.functions.getOffersTime(t).call({'from': web3.eth.accounts[3]})
        web3.parity.personal.unlockAccount(web3.eth.accounts[3], "Ukulele112", None)
        (mli) = Flexmarket_contract.functions.getOffersMaLoIdTime(t).call({'from': web3.eth.accounts[3]})

        #Filtring Offers + Sorting Offers
        if all([v == 0 for v in prc1]):
            print(f'Offers List in timestep {t} is empty\n')
            print(f'No Matching Results')
            continue
        else:
            # Dataframe For Storing Offers
            df_of = pd.DataFrame({'Flextype': np.array(flxtp1),
                            'Power': np.array(pwr1),
                            'Price': np.array(prc1),
                            'Energy': np.array(engy1),
                            'MaLoId': np.array(mli)})

            # Create Dictionary
            df_offers_dic = df_of.to_dict()
            print(f'Offers at timestep {t}:\n{df_of }\n')

            #Sorting
            df_of = df_of.sort_values(by=['Price'],kind='quicksort',ascending=False)

            #Filtering
            df_of = df_of[df_of.Energy != 0]

            print(f'Filtered and Sorted Offers price in timestep {t}\n')
            print(f'{df_of}\n')

            # Contract to push Offers into sortedoffers in BC

        #Matching
        demand_count = len(df_de)
        print(f'Demand count : {demand_count}')
        offer_count = len(df_of)
        print(f'Offer count : {offer_count}')


        df_mr = pd.DataFrame.from_dict({
            "Flextype":[],
            "DemandOwner":[],
            "MaLoId":[],
            "Price":[],
            "Power":[],
            "Energy":[],
            "Time":[],

        })

        #Matching Function off Chain
        def matching(time,df_mr):
            # Match Offers and Demands
            i = 0
            for i in range(demand_count):
                j = 0
                for j in range(offer_count):
                    if (df_offers_dic['Flextype'][j] == df_demands_dic['Flextype'][i]):  # flextype?
                        if (df_offers_dic['Price'][j] <= df_demands_dic['Price'][i]):  # is the offer price lower than the maxPrice from the DSO/TSO?
                            if (df_offers_dic['Power'][j] > df_demands_dic['Power'][i]):  # Enough power?
                                df_offers_dic['Power'][j] = df_offers_dic['Power'][j] - df_demands_dic['Power'][i]

                                if (df_offers_dic['Energy'][j] > df_demands_dic['Energy'][i]):  # Enough energy?
                                    df_offers_dic['Energy'][j] = df_offers_dic['Energy'][j] - df_demands_dic['Energy'][i]
                                    # Enough energy and power --> Match
                                    df_mr = df_mr.append({"Flextype": bool(flxtp1[j]),
                                                          "DemandOwner": df_demands_dic['DemandOwner'][i],
                                                          "MaLoId": df_offers_dic['MaLoId'][j],
                                                          "Price": df_demands_dic['Price'][i],
                                                          "Power":df_demands_dic['Power'][i],
                                                          "Energy": df_demands_dic['Energy'][i],
                                                          "Time": time}
                                                         , ignore_index=True)

                                else:# less energy offered than requested
                                    df_demands_dic['Energy'][i] = df_demands_dic['Energy'][i] - df_offers_dic['Energy'][j]
                                    df_mr = df_mr.append({"Flextype": bool(flxtp1[j]),
                                                          "DemandOwner": df_demands_dic['DemandOwner'][i],
                                                          "MaLoId": df_offers_dic['MaLoId'][j],
                                                          "Price": df_demands_dic['Price'][i],
                                                          "Power": df_demands_dic['Power'][i],
                                                          "Energy":df_offers_dic['Energy'][j],
                                                          "Time": time}
                                                         , ignore_index=True)

                            else:  #less power offered than requested
                                df_demands_dic['Power'][i] = df_demands_dic['Power'][i] - df_offers_dic['Power'][j]

                                if (df_offers_dic['Energy'][j] > df_demands_dic['Energy'][i]):  # Enough Energy?
                                    df_offers_dic['Energy'][j] = df_offers_dic['Energy'][j] - df_demands_dic['Energy'][i]
                                    df_mr = df_mr.append({"Flextype": bool(flxtp1[j]),
                                                          "DemandOwner": df_demands_dic['DemandOwner'][i],
                                                          "MaLoId": df_offers_dic['MaLoId'][j],
                                                          "Price": df_demands_dic['Price'][i],
                                                          "Power": df_offers_dic['Power'][j],
                                                          "Energy": df_demands_dic['Energy'][i],
                                                          "Time": time}
                                                         , ignore_index=True)

                                else:# less energy AND Power offered than requested
                                    df_demands_dic['Energy'][i] = df_demands_dic['Energy'][i] - df_offers_dic['Energy'][j]
                                    df_mr = df_mr.append({"Flextype": bool(flxtp1[j]),
                                                          "DemandOwner": df_demands_dic['DemandOwner'][i],
                                                          "MaLoId": df_offers_dic['MaLoId'][j],
                                                          "Price": df_demands_dic['Price'][i],
                                                          "Power": df_offers_dic['Power'][j],
                                                          "Energy": df_offers_dic['Energy'][j],
                                                          "Time": time}
                                                         , ignore_index=True)
            return df_mr

        #Matching Dataframe
        df_mr = matching(t,df_mr)
        df_mr = df_mr[~np.all(df_mr == 0, axis=1)]

        #Creates Dictionary
        df_mr_dic = df_mr.to_dict()

        #Counts number of rows
        numberofmr = df_mr.shape[0]

        print(f'Number of Matching Results: {numberofmr}\n')

        if((df_mr['Energy'] == 0).all() == True):
            print('No Matching Results\n')
            continue
        else:
            print(f'Dataframe of MatchingResults \n {df_mr} \n')
            i = 0

            #Init MatchingPairs Array on Chain
            web3.parity.personal.unlockAccount(web3.eth.accounts[3], "Ukulele112", None)
            Flexmarket_contract.functions.InitMatchingResult(int(df_mr_dic['Time'][i]),numberofmr).transact({'from': web3.eth.accounts[3]})
            print('MatchingResultsArray Initialized\n')

            #Passing the MatchingResults to the chain
            for i in range(numberofmr-1):
                time.sleep(0.1)
                print(i,bool(df_mr_dic['Flextype'][i]), int(df_mr_dic['MaLoId'][i]), int(df_mr_dic['Price'][i]), int(df_mr_dic['Power'][i]), int(df_mr_dic['Energy'][i]), int(df_mr_dic['Time'][i]), numberofmr)
                web3.parity.personal.unlockAccount(web3.eth.accounts[3], "Ukulele112", None)
                Flexmarket_contract.functions.MatchingPairTransfer(bool(df_mr_dic['Flextype'][i]), int(df_mr_dic['MaLoId'][i]), int(df_mr_dic['Price'][i]), int(df_mr_dic['Power'][i]), int(df_mr_dic['Energy'][i]), int(df_mr_dic['Time'][i]),i).transact({'from': web3.eth.accounts[3]})
                print(f'Nr {i} Transfer to Blockchain Successfull!!!')
                i = i + 1

            web3.parity.personal.unlockAccount(web3.eth.accounts[3], "Ukulele112", None)
            (flxtp, prc, pwr, engy, tm) = Flexmarket_contract.functions.getMatchingResult(t).call({'from': web3.eth.accounts[3]})
            print(f'flextype :{flxtp} ,\nprice: {prc},\npower : {pwr},\nenergy : {engy},\ntm : {tm}')

            web3.parity.personal.unlockAccount(web3.eth.accounts[3], "Ukulele112", None)
            (mli) = Flexmarket_contract.functions.getMatchingMarketID(t).call({'from': web3.eth.accounts[3]})
            print(f'MaLoId :{mli} \n')

    for t in range(95):
        print(f'Matching Results at {t}:')
        web3.parity.personal.unlockAccount(web3.eth.accounts[3], "Ukulele112", None)
        (flxtp, prc, pwr, engy, tm) = Flexmarket_contract.functions.getMatchingResult(t).call({'from': web3.eth.accounts[3]})
        print(f'Flextype :{flxtp} ,\nPrice: {prc},\nPower : {pwr},\nEnergy : {engy},\nTime : {tm}')

        web3.parity.personal.unlockAccount(web3.eth.accounts[3], "Ukulele112", None)
        (mli) = Flexmarket_contract.functions.getMatchingMarketID(t).call({'from': web3.eth.accounts[3]})
        print(f'MaLoId: {mli} \n')

    timersim = time.time() - start_timersim

    file = open('Simulation_Times.txt', 'a')

    timersim = timersim / 60

    file.write(f'The Simulation of off_chain_solution.py was {timersim}min long _ {dt.year}y{dt.month}m{dt.day}d_{dt.hour}h{dt.minute}min \n')

    file.close()
    break
                
