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

        #Functions
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
        
        def get_electrical_breaker_price(db, load_current):
            electrical_breaker_query = f'''
                SELECT `CircuitBreaker_Price`
                FROM `construction`.`electrical_breaker`
                WHERE `CircuitBreaker_Amps` > '{load_current}'
                ORDER BY `CircuitBreaker_Amps` ASC
                LIMIT 1
            '''
            electrical_breaker_query_result = db.execute(electrical_breaker_query)
            return electrical_breaker_query_result['result'][0]['CircuitBreaker_Price']
        
        def get_electrical_servicePanel_price(db, load_current):
            electrical_servicePanel_query = f'''
                SELECT `ServicePanel_Price`
                FROM `construction`.`electrical_servicePanel`
                WHERE `ServicePanel_Amps` > '{load_current}'
                ORDER BY `ServicePanel_Amps` ASC
                LIMIT 1
            '''
            electrical_servicePanel_query_result = db.execute(electrical_servicePanel_query)
            return electrical_servicePanel_query_result['result'][0]['ServicePanel_Price']
        
        def get_electrical_wire_price(db, load_current):
            electrical_wire_query = f'''
                SELECT `Wire_Price`
                FROM `construction`.`electrical_wire`
                WHERE `Wire_Load` > '{load_current}'
                ORDER BY `Wire_Load` ASC
                LIMIT 1
            '''
            electrical_wire_query_result = db.execute(electrical_wire_query)
            return electrical_wire_query_result['result'][0]['Wire_Price']
        
        def get_transformer_data(db):
            query = "SELECT * FROM `construction`.`electrical_transformer`"
            transformer_data = db.execute(query)
            transformers = transformer_data['result']

            kvas = [t['Transformer_kVa'] for t in transformers]
            prices = [t['Transformer_Price'] for t in transformers]

            return kvas, prices
        
        
        def find_all_combinations(kvas, prices, target_kva):
            all_combinations = []
            min_kva = min(kvas)

            def find_combinations(index, current_combination, current_kva, current_price, target_kva):
                if current_kva >= target_kva:
                    if current_kva <= target_kva + min_kva - 1:
                        all_combinations.append((current_combination.copy(), current_kva, current_price))
                    return

                if index == len(kvas):
                    return

                # Include current transformer (can include multiple times)
                find_combinations(index,
                                current_combination + [index],
                                current_kva + kvas[index],
                                current_price + prices[index],
                                target_kva)

                # Exclude current transformer
                find_combinations(index + 1,
                                current_combination,
                                current_kva,
                                current_price,
                                target_kva)

            find_combinations(0, [], 0, 0, target_kva)

            return all_combinations
        
        def filter_combinations(combinations, kvas, transformer_limit):
            transformer_kvas = []
            total_kva = []
            total_price = []

            transformer_array_size_limit=5

            for combination in combinations:
                indices, kva, price = combination

                if len(indices) <= transformer_limit:
                    transformer_kvas.append([kvas[i] for i in indices])
                    total_kva.append(kva)
                    total_price.append(price)


            combined = list(zip(total_price, transformer_kvas, total_kva))
            combined_sorted = sorted(combined, key=lambda x: x[0])
            top_combined = combined_sorted[:transformer_array_size_limit]
            total_price_list_sorted, transformer_kvas_list_sorted, total_kva_list_sorted = zip(*top_combined)

            return list(transformer_kvas_list_sorted), list(total_kva_list_sorted), list(total_price_list_sorted)

        
        def perform_electrical_calculation(building_sqft,small_appliances_circuit,laundry_circuit,total_fix_appliances_watts,total_other_loads_watts,total_fix_appliances_quantity,voltage,transformer_limit):

            mandate_VA=3
            small_appliances_VA=1500
            laundry_circuit_VA=1500

            electrical_transformer_list=[]
            electrical_transformer_price_list=[]

            #Electric
            if small_appliances_circuit<2:
                small_appliances_circuit=2

            general_lighting_summation=building_sqft*mandate_VA+laundry_circuit*laundry_circuit_VA+small_appliances_circuit*small_appliances_VA
            general_lighting=(general_lighting_summation-3000)*0.35+3000
            
            if total_fix_appliances_quantity>=4:
                adjusted_fix_appliances_watts=total_fix_appliances_watts*0.75
            else:
                adjusted_fix_appliances_watts=total_fix_appliances_watts

            adjusted_lightning_load_demand_factor=general_lighting+adjusted_fix_appliances_watts+total_other_loads_watts

            load_current=adjusted_lightning_load_demand_factor/voltage

            total_general_lighting=adjusted_lightning_load_demand_factor*num_of_building
            total_general_lighting_kVA=(total_general_lighting/1000)
            adjusted_total_general_lighting_kVA=(total_general_lighting/1000)/0.8 #increasing sizing by 100/80

            electrical_breaker_price=get_electrical_breaker_price(db, load_current)
            electrical_servicePanel_price=get_electrical_servicePanel_price(db,load_current)

            #Transformer
            kvas, prices = get_transformer_data(db)
            all_combinations = find_all_combinations(kvas, prices, adjusted_total_general_lighting_kVA)
            transformer_kvas, transformer_total_kva, transformer_total_price = filter_combinations(all_combinations, kvas, transformer_limit)

            
            return{
                "general_lighting": general_lighting,
                "total_general_lighting_kVA": total_general_lighting_kVA,
                "adjusted_total_general_lighting_kVA": adjusted_total_general_lighting_kVA,
                "load_current": load_current,
                "electrical_breaker_price": electrical_breaker_price,
                "electrical_servicePanel_price": electrical_servicePanel_price,
                "electrical_transformer_list": electrical_transformer_list,
                "electrical_transformer_price_list": electrical_transformer_price_list,
                "transformer_kvas": transformer_kvas,
                "transformer_total_kva": transformer_total_kva,
                "transformer_total_price": transformer_total_price
            }
        
        def perform_wiring_calculation(num_of_building, number_of_inlet, a, b, load_current, transformer_total_kva, transformer_kvas):
            first_half_sum = 0
            last_half_sum = 0

            wire_sum = []
            total_wire_cost = []

            wire_price=get_electrical_wire_price(db, load_current)

            for i in range(len(transformer_total_kva)):
                j = transformer_total_kva[i]
                first_half = 0
                
                while j > transformer_total_kva[i] / 2:
                    first_half += transformer_kvas[i][-1]
                    j -= transformer_kvas[i][-1]
                
                last_half = transformer_total_kva[i] - first_half

                first_half_ratio = first_half / transformer_total_kva[i]
                last_half_ratio = last_half / transformer_total_kva[i]

                first_half_house_to_transformer = first_half_ratio * num_of_building
                last_half_house_to_transformer = last_half_ratio * num_of_building

                first_half_house_per_side_main = first_half_house_to_transformer / number_of_inlet / 2
                last_half_house_per_side_main = last_half_house_to_transformer / number_of_inlet / 2

                first_half_sum = first_half_house_per_side_main * first_half_ratio * a * number_of_inlet
                last_half_sum = last_half_house_per_side_main * last_half_ratio * a * number_of_inlet
                lateral_sum = b / 2 / (number_of_inlet * 4) * num_of_building

                wire_sum.append(first_half_sum + last_half_sum + lateral_sum)
                total_wire_cost.append(wire_sum[i] * wire_price *3) #groud+live+neutral=3

            return total_wire_cost
                
        
        def perform_water_calculations(db, total_wsfu, total_dfu, num_of_building, unit_per_building, a, b, city_pressure_psi, main_drain_slope, load_current, transformer_total_kva, transformer_kvas):
            num_of_inlet = 1
            min_price = 99999999
            counter = 0
            index = 0

            number_of_inlet_list=[]

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

            wiring_price_list=[]

            trench_cost = 2.5
            trench_total_price_list = []

            total_price_list = []
            

            while counter < 3:
                number_of_inlet_list=num_of_inlet
                #Pipe Size Lookup
                main_water_supply_wsfu = total_wsfu * num_of_building / num_of_inlet
                main_water_supply_pipe_size = get_water_supply_pipe_size(db, main_water_supply_wsfu, city_pressure_psi)
                main_water_supply_pipe_size_list.append(main_water_supply_pipe_size)

                lateral_water_supply_wsfu = total_wsfu / unit_per_building
                lateral_water_supply_pipe_size = get_water_supply_pipe_size(db, lateral_water_supply_wsfu, city_pressure_psi)
                lateral_water_supply_pipe_size_list.append(lateral_water_supply_pipe_size)

                main_drain_dfu = total_dfu * num_of_building/ num_of_inlet
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

                lateral_water_supply_pipe_quantity = num_of_building / unit_per_building
                lateral_water_supply_pipe_length = b / 2 / (num_of_inlet * 2)
                lateral_total_price = lateral_water_supply_pipe_length * lateral_water_supply_pipe_quantity * lateral_water_supply_pvc_price
                lateral_water_supply_total_price_list.append(lateral_total_price)

                main_drain_total_price = main_drain_pvc_price * a * num_of_inlet
                main_drain_total_price_list.append(main_drain_total_price)

                lateral_drain_total_price = lateral_water_supply_pipe_length * lateral_water_supply_pipe_quantity * lateral_drain_pvc_price
                lateral_drain_total_price_list.append(lateral_drain_total_price)

                result_wiring_price=perform_wiring_calculation(num_of_building, num_of_inlet, a, b, load_current, transformer_total_kva, transformer_kvas)
                wiring_price_list.append(result_wiring_price)

                trench_dimension = (a * num_of_inlet) + (lateral_water_supply_pipe_length * lateral_water_supply_pipe_quantity)
                trench_pipe_price = trench_dimension * trench_cost

                trench_electrical_dimension = (num_of_inlet/(1+num_of_inlet))*b
                trench_electric_price = trench_electrical_dimension*trench_cost

                trench_total_price_list.append(trench_pipe_price+trench_electric_price)

                #Total Price Calculate
                total_price = main_water_supply_total_price + lateral_total_price + main_drain_total_price + lateral_drain_total_price + trench_pipe_price 
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
                "number_of_inlet_list": number_of_inlet_list,
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
                "trench_pipe_price": trench_total_price_list,
                "total_price_list": total_price_list,
                "min_inlet_num": min_inlet_num,
                "min_price": min_price,
                "wiring_price_list": wiring_price_list,
            }
        
        with connect() as db:
            #JSON user Input
            city_pressure_psi = payload['City Pressure (PSI)']
            water_supply_fixture = payload['Water Supply Fixture']
            drain_fixture = payload['Drain Fixture']
            main_drain_slope = payload['Drain Slope']
            num_of_building = int(payload['Number of Building'])
            unit_per_building = int(payload['Units Per Building'])
            plot_length = float(payload['Plot Length'])
            plot_width = float(payload['Plot Width'])
            electrical_appliances=payload['Electrical Appliances']
            building_sqft=payload['Building Plot Dimension sqft']
            small_appliances_circuit=int(payload['Small Appliances Circuit'])
            laundry_circuit=int(payload['Laundry Circuit'])
            city_water_supply_pipe=float(payload['City Water Supply Pipe Size'])
            city_drain_pipe=float(payload['City Drain Pipe Size'])
            voltage=int(payload['Voltage'])
            transformer_limit=int(payload['Transformers Limit'])

            water_supply_fixture_str = '(' + ', '.join([f"'{water_supply_item}'" for water_supply_item in water_supply_fixture]) + ')'
            drain_fixture_str = '(' + ', '.join([f"'{drain_item}'" for drain_item in drain_fixture]) + ')'
            electrical_appliances_appliances_str = '(' + ', '.join([f"'{electrical_appliances_item}'" for electrical_appliances_item in electrical_appliances]) + ')'

            #MySQL Query
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

            fix_appliances_query = f'''
                SELECT SUM(Power_Consumption_Watts) AS TotalFixAppliancesWatts,
                    COUNT(*) AS FixApplianceCount
                FROM `construction`.`electrical_appliances`
                WHERE Electric_Item_ID IN {electrical_appliances_appliances_str}
                AND Appliances_Type = 'Fix_Appliances'
            '''

            fix_appliances_result = db.execute(fix_appliances_query)
            total_fix_appliances_watts = int(fix_appliances_result['result'][0]['TotalFixAppliancesWatts'])
            total_fix_appliances_quantity = int(fix_appliances_result['result'][0]['FixApplianceCount'])


            other_loads_query = f'''
                SELECT SUM(Power_Consumption_Watts) AS TotalOtherLoadsWatts
                FROM `construction`.`electrical_appliances`
                WHERE Electric_Item_ID IN {electrical_appliances_appliances_str}
                AND Appliances_Type = 'Other_Loads'
            '''

            other_loads_result = db.execute(other_loads_query)
            total_other_loads_watts = int(other_loads_result['result'][0]['TotalOtherLoadsWatts'])

            result_electric=perform_electrical_calculation(building_sqft,small_appliances_circuit,laundry_circuit,total_fix_appliances_watts,total_other_loads_watts,total_fix_appliances_quantity,voltage,transformer_limit)
            resultLength = perform_water_calculations(db, total_wsfu, total_dfu, num_of_building, unit_per_building, plot_length, plot_width, city_pressure_psi, main_drain_slope, result_electric['load_current'], result_electric['transformer_total_kva'], result_electric['transformer_kvas'])
            resultWidth = perform_water_calculations(db, total_wsfu, total_dfu, num_of_building, unit_per_building, plot_width, plot_length, city_pressure_psi, main_drain_slope, result_electric['load_current'], result_electric['transformer_total_kva'], result_electric['transformer_kvas'])
            
            # #Calculate Min Price
            # if resultLength["min_price"] > resultWidth["min_price"]:
            #     grand_min_price = resultWidth["min_price"]
            #     grand_min_inlet = resultWidth["min_inlet_num"]
            #     pipe_direction = "Width"
            # else:
            #     grand_min_price = resultLength["min_price"]
            #     grand_min_inlet = resultLength["min_inlet_num"]
            #     pipe_direction = "Length"

            # if resultLength["min_price"] == resultWidth["min_price"]:
            #     grand_min_price = resultWidth["min_price"]
            #     grand_min_inlet = resultWidth["min_inlet_num"]
            #     pipe_direction = "Width and Length are the SAME"


            response = {         
                # User Input
                "City Pressure (PSI)": city_pressure_psi,
                "Number of Building": num_of_building,
                "Units Per Building": unit_per_building,
                "Plot Length": plot_length,
                "Plot Width": plot_width,   
                "Building sqft": building_sqft,

            
                "Water Supply Fixture Unit Per Building": total_wsfu,
                "Total Water Supply Fixture Unit": total_wsfu * num_of_building,
                "Drain Fixture Unit Per Building": total_dfu,
                "Total Drain Fixture Unit": total_dfu * num_of_building,
                "Drain Slope Configuration": main_drain_slope,

                "Electrical Appliances": electrical_appliances,
                "Small Appliances Circuit": small_appliances_circuit,

                "Water Supply Fixture List": water_supply_fixture,
                "Drain Fixture List": drain_fixture,
                "Laundry Circuit List": laundry_circuit,

                # Output
                # "Minimum Cost Configuration": [
                #     {
                #         "Configuration": pipe_direction + " " + str(grand_min_inlet),
                #         "Number of Inlet": grand_min_inlet,
                #         "Min Price": grand_min_price,
                #     }
                # ],

                "Length Configuration Results": [
                    {
                        "Configuration": f"Length {i+1}.{j+1}",
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

                        "Electrical": [
                            {
                                "Total Fix Appliances Watts": total_fix_appliances_watts,
                                "Total Other Loads Watts": total_other_loads_watts,
                                "Voltage": voltage,
                                "General Lighting Per Housing": result_electric['general_lighting'],
                                "Total General Lighting kVA": result_electric['total_general_lighting_kVA'],
                                "Load Current": result_electric['load_current'],
                                "Electrical Breaker Price": result_electric['electrical_breaker_price'],
                                "Electrical Service Panel Price": result_electric['electrical_servicePanel_price'],
                                "Electrical Transformer Configurations": [
                                    {
                                        "Transformer Configuration": f"{j+1}",
                                        "Transformers": result_electric['transformer_kvas'][j],
                                        "Total kVA": result_electric['transformer_total_kva'][j],
                                        "Total Transformer Price": result_electric['transformer_total_price'][j],
                                        "Total Wiring Price": resultLength['wiring_price_list'][i][j],
                                        "Total Electrical Price": result_electric['transformer_total_price'][j] + resultLength['wiring_price_list'][i][j],
                                    }
                                    
                                ]
                            }
                        ],

                        "Total Cost":[
                            {
                                "Main Water Supply Pipe Price": resultLength['main_water_supply_total_price_list'][i],
                                "Lateral Water Supply Pipe Price": resultLength['lateral_water_supply_total_price_list'][i],
                                "Main Drain Pipe Price": resultLength['main_drain_total_price_list'][i],
                                "Lateral Drain Pipe Price": resultLength['lateral_drain_total_price_list'][i],
                                "Electric Price": result_electric['transformer_total_price'][j] + resultLength['wiring_price_list'][i][j],
                                "Trench Price": resultLength['trench_pipe_price'][i],
                                "Total Electrical Price": result_electric['transformer_total_price'][j] + resultLength['wiring_price_list'][i][j],
                                "Total Sum": resultLength['total_price_list'][i]+ result_electric['transformer_total_price'][j] + resultLength['wiring_price_list'][i][j],
                            }
                        ]

                    }
                    for i in range(len(resultLength['main_water_supply_pipe_size_list']))
                        for j in range(len(result_electric['transformer_total_price']))
                            if i < len(resultLength['main_water_supply_pipe_size_list']) and \
                            i < len(resultLength['main_drain_pipe_size_list']) and \
                            resultLength['main_water_supply_pipe_size_list'][i] < city_water_supply_pipe and \
                            resultLength['main_drain_pipe_size_list'][i] < city_drain_pipe
                ],

                "Width Results": [
                    {
                        "Configuration": f"Width {i+1}.{j+1}",
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


                        "Electrical": [
                            {
                                "Total Fix Appliances Watts": total_fix_appliances_watts,
                                "Total Other Loads Watts": total_other_loads_watts,
                                "Voltage": voltage,
                                "General Lighting Per Housing": result_electric['general_lighting'],
                                "Total General Lighting kVA": result_electric['total_general_lighting_kVA'],
                                "Load Current": result_electric['load_current'],
                                "Electrical Breaker Price": result_electric['electrical_breaker_price'],
                                "Electrical Service Panel Price": result_electric['electrical_servicePanel_price'],
                                "Electrical Transformer Configurations": [
                                    {
                                        "Transformer Configuration": f"{j+1}",
                                        "Transformers": result_electric['transformer_kvas'][j],
                                        "Total kVA": result_electric['transformer_total_kva'][j],
                                        "Total Transformer Price": result_electric['transformer_total_price'][j],
                                        "Total Wiring Price": resultWidth['wiring_price_list'][i][j],
                                        "Total Electrical Price": result_electric['transformer_total_price'][j] + resultWidth['wiring_price_list'][i][j],
                                    }
                                    
                                ]
                            }
                        ],

                        "Total Cost":[
                            {
                                "Main Water Supply Pipe Price": resultWidth['main_water_supply_total_price_list'][i],
                                "Lateral Water Supply Pipe Price": resultWidth['lateral_water_supply_total_price_list'][i],
                                "Main Drain Pipe Price": resultWidth['main_drain_total_price_list'][i],
                                "Lateral Drain Pipe Price": resultWidth['lateral_drain_total_price_list'][i],
                                "Electric Price": result_electric['transformer_total_price'][j] + resultLength['wiring_price_list'][i][j],
                                "Trench Price": resultWidth['trench_pipe_price'][i],
                                "Total Electrical Price": result_electric['transformer_total_price'][j] + resultWidth['wiring_price_list'][i][j],
                                "Total Sum": resultWidth['total_price_list'][i]+result_electric['transformer_total_price'][j] + resultWidth['wiring_price_list'][i][j],
                            }
                        ]

                    }
                    for i in range(len(resultWidth['main_water_supply_pipe_size_list']))
                        for j in range(len(result_electric['transformer_total_price']))
                            if i < len(resultWidth['main_water_supply_pipe_size_list']) and \
                            i < len(resultWidth['main_drain_pipe_size_list']) and \
                            resultWidth['main_water_supply_pipe_size_list'][i] < city_water_supply_pipe and \
                            resultWidth['main_drain_pipe_size_list'][i] < city_drain_pipe
                ]
            }

            return response

api.add_resource(Estimator, '/estimator')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=4000)