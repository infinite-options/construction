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
    
    def post(self):
        print('Estimator API Post')
        response = {}
        payload = request.get_json()

        def get_water_supply_pipe_size(db, wsfu, city_pressure_psi):
            water_supply_pipe_query = f'''
                SELECT Main_Size
                FROM `construction`.`inlet_pipe`
                WHERE Total_WSFU_Minimum <= {wsfu}
                    AND Total_WSFU_Maximum >= {wsfu}
                    AND Pressure_Range_Minimum <= {city_pressure_psi}
                    AND Pressure_Range_Maximum >= {city_pressure_psi}
            '''
            main_water_supply_pipe_result = db.execute(water_supply_pipe_query)
            return main_water_supply_pipe_result['result'][0]['Main_Size']
        
        def get_main_drain_pipe_size(db, main_drain_dfu, slope):
            main_drain_pipe_query = f'''
                SELECT Pipe_Size
                FROM `construction`.`outlet_drain`
                WHERE {slope} > {main_drain_dfu}
                    AND Pipe_Size >= 3
                ORDER BY C ASC
                LIMIT 1
            '''
            main_drain_pipe_result = db.execute(main_drain_pipe_query)
            return main_drain_pipe_result['result'][0]['Pipe_Size']
        
        def get_lateral_drain_pipe_size(db, lateral_drain_dfu):
            lateral_drain_pipe_query = f'''
                SELECT Pipe_Size
                FROM `construction`.`outlet_horizontal`
                WHERE Horizontal_Fixture_Branches > {lateral_drain_dfu}
                    AND Pipe_Size >= 3
                ORDER BY Horizontal_Fixture_Branches ASC
                LIMIT 1
            '''
            lateral_drain_pipe_result = db.execute(lateral_drain_pipe_query)
            return lateral_drain_pipe_result['result'][0]['Pipe_Size']

        def get_pvc_price(db, main_pipe_size):
            pvc_query = f'''
                SELECT `PVC_Price`
                FROM `construction`.`pvc`
                WHERE `PVC_Size` = '{main_pipe_size}'
            '''
            pvc_result = db.execute(pvc_query)
            return pvc_result['result'][0]['PVC_Price']

        def perform_calculations(db, total_wsfu, total_dfu, num_of_housing, unit_per_housing, a, b, city_pressure_psi, main_drain_slope):
            num_of_inlet = 1
            min_price = 99999999
            min_index = 99999999
            counter = 0
            index = 0

            main_water_supply_pipe_size_list = []
            main_water_supply_pvc_price_list = []
            main_water_supply_total_price_list = []

            lateral_water_supply_pipe_size_list = []
            lateral_water_supply_pvc_price_list = []
            lateral_water_supply_total_price_list = []

            main_drain_pipe_size_list = []
            main_drain_pvc_price_list = []
            main_drain_total_price_list = []

            lateral_drain_pipe_size_list = []
            lateral_drain_pvc_price_list = []
            lateral_drain_total_price_list = []

            trench_cost = 2.5
            trench_total_price_list = []

            total_price_list = []

            while counter < 3:
                #Pipe Size Lookup
                main_water_supply_wsfu = total_wsfu * num_of_housing / num_of_inlet
                main_water_supply_pipe_size = get_water_supply_pipe_size(db, main_water_supply_wsfu, city_pressure_psi)
                main_water_supply_pipe_size_list.append(main_water_supply_pipe_size)

                lateral_water_supply_wsfu = total_wsfu / unit_per_housing
                lateral_water_supply_pipe_size = get_water_supply_pipe_size(db, lateral_water_supply_wsfu, city_pressure_psi)
                lateral_water_supply_pipe_size_list.append(lateral_water_supply_pipe_size)

                main_drain_dfu = total_dfu * num_of_housing / num_of_inlet
                main_drain_pipe_size = get_main_drain_pipe_size(db, main_drain_dfu, main_drain_slope)
                main_drain_pipe_size_list.append(main_drain_pipe_size)

                lateral_drain_dfu = total_dfu
                lateral_drain_pipe_size = get_lateral_drain_pipe_size(db, lateral_drain_dfu)
                lateral_drain_pipe_size_list.append(lateral_drain_pipe_size)

                #PVC Price Lookup
                main_water_supply_pvc_price = get_pvc_price(db, main_water_supply_pipe_size)
                main_water_supply_pvc_price_list.append(main_water_supply_pvc_price)

                lateral_water_supply_pvc_price = get_pvc_price(db, lateral_water_supply_pipe_size)
                lateral_water_supply_pvc_price_list.append(lateral_water_supply_pvc_price)

                main_drain_pvc_price = get_pvc_price(db, main_drain_pipe_size)
                main_drain_pvc_price_list.append(main_drain_pvc_price)

                lateral_drain_pvc_price = get_pvc_price(db, lateral_drain_pipe_size)
                lateral_drain_pvc_price_list.append(lateral_drain_pvc_price)

                #Price Calculation
                main_water_supply_total_price = main_water_supply_pvc_price * a * num_of_inlet
                main_water_supply_total_price_list.append(main_water_supply_total_price)

                lateral_water_supply_pipe_quantity = num_of_housing / unit_per_housing
                lateral_water_supply_pipe_length = b / 2 / (num_of_inlet * 2)
                lateral_total_price = lateral_water_supply_pipe_length * lateral_water_supply_pipe_quantity * lateral_water_supply_pvc_price
                lateral_water_supply_total_price_list.append(lateral_total_price)

                main_drain_total_price = main_drain_pvc_price * a * num_of_inlet
                main_drain_total_price_list.append(main_drain_total_price)

                lateral_drain_total_price = lateral_water_supply_pipe_length * lateral_water_supply_pipe_quantity * lateral_drain_pvc_price
                lateral_drain_total_price_list.append(lateral_drain_total_price)

                trench_dimension = (a * num_of_inlet) + (lateral_water_supply_pipe_length * lateral_water_supply_pipe_quantity)
                trench_price = trench_dimension * trench_cost
                trench_total_price_list.append(trench_price)

                #Total Price Calculate
                total_price = main_water_supply_total_price + lateral_total_price + main_drain_total_price + lateral_drain_total_price + trench_price
                total_price_list.append(total_price)

                if min_price > total_price:
                    min_price = total_price
                    min_index = num_of_inlet - 1
                    min_inlet_num = num_of_inlet

                if index > 1:
                    if total_price_list[index] > total_price_list[index - 1]:
                        counter += 1
                    else:
                        counter = 0

                index += 1
                num_of_inlet += 1

            return {
                "main_water_supply_pipe_size_list": main_water_supply_pipe_size_list,
                "main_water_supply_pvc_price_list": main_water_supply_pvc_price_list,
                "main_water_supply_total_price_list": main_water_supply_total_price_list,
                "lateral_water_supply_pipe_size_list": lateral_water_supply_pipe_size_list,
                "lateral_water_supply_pvc_price_list": lateral_water_supply_pvc_price_list,
                "lateral_water_supply_total_price_list": lateral_water_supply_total_price_list,
                "main_drain_pipe_size_list": main_drain_pipe_size_list,
                "main_drain_pvc_price_list": main_drain_pvc_price_list,
                "main_drain_total_price_list": main_drain_total_price_list,
                "lateral_drain_pipe_size_list": lateral_drain_pipe_size_list,
                "lateral_drain_pvc_price_list": lateral_drain_pvc_price_list,
                "lateral_drain_total_price_list": lateral_drain_total_price_list,
                "trench_price": trench_total_price_list,
                "total_price_list": total_price_list,
                "min_inlet_num": min_inlet_num,
                "min_price": min_price
            }

        with connect() as db:
            city_pressure_psi = payload['City Pressure (PSI)']
            water_supply_fixture = payload['Water Supply Fixture']
            drain_fixture = payload['Drain Fixture']
            main_drain_slope = payload['Drain Slope']
            num_of_housing = int(payload['Number of Housing'])
            unit_per_housing = int(payload['Units Per Housing'])
            plot_length = float(payload['Plot Length'])
            plot_width = float(payload['Plot Width'])

            water_supply_fixture_str = '(' + ', '.join([f"'{water_supply_item}'" for water_supply_item in water_supply_fixture]) + ')'
            drain_fixture_str = '(' + ', '.join([f"'{drain_item}'" for drain_item in drain_fixture]) + ')'

            wsfu_query = f'''
                SELECT SUM(Total_WSFU) AS TotalWSFU
                FROM (
                    SELECT Inlet_WSFU_ID, SUM(`Inlet_Private_WSFU`) AS Total_WSFU
                    FROM `construction`.`inlet_wsfu`
                    WHERE Inlet_WSFU_ID IN {water_supply_fixture_str}
                    GROUP BY Inlet_WSFU_ID
                ) AS w
            '''
            wsfu_result = db.execute(wsfu_query)
            total_wsfu = int(wsfu_result['result'][0]['TotalWSFU'])

            dfu_query = f'''
                SELECT SUM(Total_DFU) AS TotalDFU
                FROM (
                    SELECT Outlet_DFU_ID, SUM(`Outlet_Private_DFU`) AS Total_DFU
                    FROM `construction`.`outlet_dfu`
                    WHERE Outlet_DFU_ID IN {drain_fixture_str}
                    GROUP BY Outlet_DFU_ID
                ) AS w
            '''

            dfu_result = db.execute(dfu_query)
            total_dfu = int(dfu_result['result'][0]['TotalDFU'])

            resultLength = perform_calculations(db, total_wsfu, total_dfu, num_of_housing, unit_per_housing, plot_length, plot_width, city_pressure_psi, main_drain_slope)
            resultWidth = perform_calculations(db, total_wsfu, total_dfu, num_of_housing, unit_per_housing, plot_width, plot_length, city_pressure_psi, main_drain_slope)

            if resultLength["min_price"] > resultWidth["min_price"]:
                grand_min_price = resultWidth["min_price"]
                grand_min_inlet = resultWidth["min_inlet_num"]
                pipe_direction = "Width"
            else:
                grand_min_price = resultLength["min_price"]
                grand_min_inlet = resultLength["min_inlet_num"]
                pipe_direction = "Length"

            if resultLength["min_price"] == resultWidth["min_price"]:
                grand_min_price = resultWidth["min_price"]
                grand_min_inlet = resultWidth["min_inlet_num"]
                pipe_direction = "Width and Length are the SAME"

            response = {                
                "Water Supply Fixture": water_supply_fixture,
                "Drain Fixture":drain_fixture,
                "Drain Slope Configuration":main_drain_slope,
                "City Pressure (PSI)":city_pressure_psi,
                "Number of Housing": num_of_housing,
                "Units Per Housing": unit_per_housing,
                "Plot Length": plot_length,
                "Plot Width": plot_width,

                "Minimum Cosst Configuretion": [
                    {
                    "Configuration": pipe_direction + " " + str(grand_min_inlet),
                    "Inlet Number": grand_min_inlet,
                    "Min Price": grand_min_price,
                    }
                ],
                
                "Length Configuration Results": [
                    {
                        "Configuration": f"Length {i+1}",
                        "Number of Inlet": i+1,

                        "Water Supply":[
                            {
                                "Main":[
                                    {
                                    "Main Water Supply Pipe Size": resultLength['main_water_supply_pipe_size_list'][i],
                                    "Main Water Supply Pipe PVC Price": resultLength['main_water_supply_pvc_price_list'][i],
                                    "Main Water Supply Pipe Price": resultLength['main_water_supply_total_price_list'][i],
                                    }
                                ],
                                "Lateral":[
                                    {
                                    "Lateral Water Supply Pipe Size": resultLength['lateral_water_supply_pipe_size_list'][i],
                                    "Lateral Water Supply Pipe PVC Price": resultLength['lateral_water_supply_pvc_price_list'][i],
                                    "Lateral Water Supply Pipe Price": resultLength['lateral_water_supply_total_price_list'][i],
                                    }
                                ],
                            }
                        ],

                        "Drain":[
                            {
                                "Main":[
                                    {
                                    "Main Drain Pipe Size": resultLength['main_drain_pipe_size_list'][i],
                                    "Main Drain Pipe PVC Price": resultLength['main_drain_pvc_price_list'][i],
                                    "Main Drain Pipe Price": resultLength['main_drain_total_price_list'][i],
                                    }
                                ],
                                "Lateral":[
                                    {
                                    "Lateral Drain Pipe Size": resultLength['lateral_drain_pipe_size_list'][i],
                                    "Lateral Drain Pipe PVC Price": resultLength['lateral_drain_pvc_price_list'][i],
                                    "Lateral Drain Pipe Price": resultLength['lateral_drain_total_price_list'][i],
                                    }
                                ],
                            }
                        ],

                        "Total Cost":[
                            {
                            "Main Water Supply Pipe Price": resultLength['main_water_supply_total_price_list'][i],
                            "Lateral Water Supply Pipe Price": resultLength['lateral_water_supply_total_price_list'][i],
                            "Main Drain Pipe Price": resultLength['main_drain_total_price_list'][i],
                            "Lateral Drain Pipe Price": resultLength['lateral_drain_total_price_list'][i],
                            "Trench Price": resultLength['trench_price'][i],
                            "Total Price": resultLength['total_price_list'][i]
                            }
                        ]

                    }
                    for i in range(len(resultLength['main_water_supply_pipe_size_list']))
                ],
                "Width Results": [
                    {
                        "Configuration": f"Length {i+1}",
                        "Number of Inlet": i+1,

                        "Water Supply":[
                            {
                                "Main":[
                                    {
                                    "Main Water Supply Pipe Size": resultWidth['main_water_supply_pipe_size_list'][i],
                                    "Main Water Supply Pipe PVC Price": resultWidth['main_water_supply_pvc_price_list'][i],
                                    "Main Water Supply Pipe Price": resultWidth['main_water_supply_total_price_list'][i],
                                    }
                                ],
                                "Lateral":[
                                    {
                                    "Lateral Water Supply Pipe Size": resultWidth['lateral_water_supply_pipe_size_list'][i],
                                    "Lateral Water Supply Pipe PVC Price": resultWidth['lateral_water_supply_pvc_price_list'][i],
                                    "Lateral Water Supply Pipe Price": resultWidth['lateral_water_supply_total_price_list'][i],
                                    }
                                ],
                            }
                        ],

                        "Drain":[
                            {
                                "Main":[
                                    {
                                    "Main Drain Pipe Size": resultWidth['main_drain_pipe_size_list'][i],
                                    "Main Drain Pipe PVC Price": resultWidth['main_drain_pvc_price_list'][i],
                                    "Main Drain Pipe Price": resultWidth['main_drain_total_price_list'][i],
                                    }
                                ],
                                "Lateral":[
                                    {
                                    "Lateral Drain Pipe Size": resultWidth['lateral_drain_pipe_size_list'][i],
                                    "Lateral Drain Pipe PVC Price": resultWidth['lateral_drain_pvc_price_list'][i],
                                    "Lateral Drain Pipe Price": resultWidth['lateral_drain_total_price_list'][i],
                                    }
                                ],
                            }
                        ],

                        "Total Cost":[
                            {
                            "Main Water Supply Pipe Price": resultLength['main_water_supply_total_price_list'][i],
                            "Lateral Water Supply Pipe Price": resultLength['lateral_water_supply_total_price_list'][i],
                            "Main Drain Pipe Price": resultLength['main_drain_total_price_list'][i],
                            "Lateral Drain Pipe Price": resultLength['lateral_drain_total_price_list'][i],
                            "Trench Price": resultWidth['trench_price'][i],
                            "Total Price": resultWidth['total_price_list'][i]
                            }
                        ]

                    }
                    for i in range(len(resultWidth['main_water_supply_pipe_size_list']))
                ]
            }



        return response

api.add_resource(Estimator, '/estimator')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=4000)