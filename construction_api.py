from data_pm import connect
import json
from flask import Flask, request
from flask_restful import Resource, Api
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.config['DEBUG'] = True
api = Api(app)

class Estimator(Resource):
    
    # def get(self):
    #     print('Estimator API')
    #     response = {}

    #     with connect() as db:
    #         # Calculate the total WSFU first
    #         catalogQuery = db.execute('''
    #         SELECT *
    #         FROM `Inlet`.`inlet_pipe`
    #         WHERE Total_WSFU_Minimum <= 40 
    #         AND Total_WSFU_Maximum >= 40
    #         AND Pressure_Range_Minimum <= 40
    #         AND Pressure_Range_Maximum >= 40;
    #         ''')
    #         response["estimator"] = catalogQuery
    #     return response

    def post(self):
        print('Estimator API Post')
        response = {}
        payload = request.get_json()

        print('Estimator Payload: ', payload)
        pressure = payload['PRESSURE']
        fixture = payload['FIXTURE']
        housingUnit = payload['HOUSINGUNIT']
        unitperhousing = payload['UNITPERHOUSING']
        length=payload['LENGTH']

        with connect() as db:
            # Calculate Total WSFU
            wsfu_query  = '''
                SELECT SUM(Total_WSFU) AS TotalWSFU
                FROM (
                    SELECT Inlet_WSFU_ID, SUM(`Inlet_Private_WSFU`) AS Total_WSFU
                    FROM `Inlet`.`inlet_wsfu`
                    WHERE Inlet_WSFU_ID IN ('101-001', '101-003', '101-005', '101-007', '101-016')
                    GROUP BY Inlet_WSFU_ID
                    ) AS w
                    '''
            wsfu_result = db.execute(wsfu_query)
            total_wsfu = wsfu_result['result'][0]['TotalWSFU'] * housingUnit

            print('Total WSFU:', total_wsfu)

            # Find Pipe Inlet Size Based on Total WSFU
            inlet_pipe_query = f'''
                SELECT Main_Size
                FROM `Inlet`.`inlet_pipe`
                WHERE Total_WSFU_Minimum <= {total_wsfu}
                    AND Total_WSFU_Maximum >= {total_wsfu}
                    AND Pressure_Range_Minimum <= {pressure}
                    AND Pressure_Range_Maximum >= {pressure}
            '''
            main_pipe_result = db.execute(inlet_pipe_query)

            main_pipe_size = main_pipe_result['result'][0]['Main_Size']
            print('Main Pipe Size:', main_pipe_size)

            #Find PVC Price
            pvc_query = (f'''
                SELECT `PVC_Price`
                FROM `Inlet`.`pvc`
                WHERE `PVC_Size` = {main_pipe_size}
                ''')
            
            pvc_result = db.execute(pvc_query)

            pvc_price = pvc_result['result'][0]['PVC_Price']
            print('PVC Result:', pvc_price)

            #Total Price
            total_price = pvc_price*length




            response["Total PRICE"] = total_price
        return response

api.add_resource(Estimator, '/estimator')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=4000)