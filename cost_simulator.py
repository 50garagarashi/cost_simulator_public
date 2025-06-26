# コストシミュレータ streamlitによるアプリケーション化 
# 2025/1/6

# ライブラリのインポート
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots 
import numpy as np
import pandas as pd
from collections import OrderedDict
import translation_mapping as tm # 日本語英語対応外部モジュール
import logging
from datetime import datetime

st.set_page_config(
    page_title='NCT wafer cost simulator',
    page_icon=':heavy_dollar_sign:',
    layout='wide',
)

# ログの設定
logging.basicConfig(
    filename='simulation.log',        # ログファイル名
    level=logging.INFO,               # ログレベル
    format='%(asctime)s - %(message)s',  # ログのフォーマット
    datefmt='%Y-%m-%d %H:%M:%S'        # 日時のフォーマット
)

# サイドバーでナビゲーションメニューを表示
st.sidebar.title("関連ページリンク")
with st.sidebar:
    st.page_link("http://10.58.167.186/barcode/_module/read_pdf.php?file_name=cost_modeling_review",label="原価企画レビュー資料")
    st.page_link("http://10.58.167.186/cost_simulator/cost_flow.svg",label="原価算出フロー")
    st.page_link("http://10.58.167.186:8510/?product_split_count_comp=11&batch_process_quantity_comp=1&annual_process_capacity_per_unit_comp=168&unit_cost_comp=55000000&depreciation_period_comp=8&yield_rate_comp=80&material_cost_per_process_comp=87290&labor_cost_per_hour_comp=2960&labor_hours_per_process_comp=8.8&auxiliary_material_cost_per_process_comp=37000&utility_cost_per_process_comp=32500&maintenance_cost_per_process_comp=66110&subcontract_cost_per_process_comp=0&other_cost_per_process_comp=1000&consumables_cost_per_process_comp=100&depreciation_rate_comp=100&operating_rate_comp=100",
                 label="Bモデルシミュレータ(バルク育成工程)")
    st.page_link("http://10.58.167.186:8510/?product_split_count_comp=1&batch_process_quantity_comp=1&annual_process_capacity_per_unit_comp=319&unit_cost_comp=133631919&depreciation_period_comp=8&yield_rate_comp=98.3&material_cost_per_process_comp=10379&labor_cost_per_hour_comp=2960&labor_hours_per_process_comp=8.65&auxiliary_material_cost_per_process_comp=30756&utility_cost_per_process_comp=9567&maintenance_cost_per_process_comp=6561&subcontract_cost_per_process_comp=0&other_cost_per_process_comp=0&consumables_cost_per_process_comp=100&depreciation_rate_comp=100&operating_rate_comp=100",
                 label="Bモデルシミュレータ(エピ成長工程)")


###################################################################################
# コスト計算クラス
class ProcessCost:
    def __init__(self, product_split_count, batch_process_quantity, annual_process_capacity_per_unit, num_of_units, unit_cost, depreciation_period, yield_rate, material_cost_per_process, labor_cost_per_hour, labor_hours_per_process, auxiliary_material_cost_per_process, utility_cost_per_process, maintenance_cost_per_process, subcontract_cost_per_process, other_cost_per_process, upstream_total_annual_production, upstream_total_product_cost, cost_allocation_ratio_100mm, production_ratio_100mm, depreciation_allocation_ratio, maintenance_cost_allocation_ratio, consumables_cost_per_process, common_consumables_allocation_ratio, annual_depreciation_common_equipments, labor_cost_indirect_direct_ratio, annual_maintenance_common_equipment_cost, annual_common_consumables_cost):
        # input 
        self.product_split_count = product_split_count #製品分割数[pcs/pcs]
        self.batch_process_quantity = batch_process_quantity #バッチ処理数量[pcs/run]
        self.annual_process_capacity_per_unit = annual_process_capacity_per_unit #装置1台の年間工程キャパシティ[run/year]
        self.num_of_units = num_of_units #装置台数[unit]
        self.unit_cost = unit_cost #装置単価[yen/unit]
        self.depreciation_period = depreciation_period #装置減価償却期間[year]
        self.yield_rate = yield_rate #歩留まり[%]
        self.material_cost_per_process = material_cost_per_process #1工程あたりの材料費[yen/run]
        self.labor_cost_per_hour = labor_cost_per_hour #労務費単価[yen/h]
        self.labor_hours_per_process = labor_hours_per_process #1工程あたりの人工数[h/run]
        self.auxiliary_material_cost_per_process = auxiliary_material_cost_per_process #1工程あたりの補助材料費[yen/run]
        self.utility_cost_per_process = utility_cost_per_process #1工程あたりの水光熱費[yen/run]
        self.maintenance_cost_per_process = maintenance_cost_per_process #1工程あたりの保守維持費[yen/run]
        self.subcontract_cost_per_process = subcontract_cost_per_process #1工程あたりの外注加工費[yen/run]
        self.other_cost_per_process = other_cost_per_process #1工程あたりのその他費用[yen/run]
        self.upstream_total_annual_production = upstream_total_annual_production #前工程の中間製品の総年間生産数量[pcs/year]
        self.upstream_total_product_cost = upstream_total_product_cost #前工程の中間製品の総コスト[yen/pcs]
        # 24/8/8追加input
        self.production_ratio_100mm = production_ratio_100mm #100mm品製造比率[%]
        self.cost_allocation_ratio_100mm = cost_allocation_ratio_100mm #100mm品製造コスト比率[%]
        self.depreciation_allocation_ratio = depreciation_allocation_ratio #共通設備の減価償却費の配賦比率[%]
        self.maintenance_cost_allocation_ratio = maintenance_cost_allocation_ratio #共通設備の保守維持費の配賦比率[%]
        self.consumables_cost_per_process = consumables_cost_per_process #1工程あたりの消耗品費[yen/run]
        self.common_consumables_allocation_ratio = common_consumables_allocation_ratio #共通消耗品費の配賦比率[%]

        # metadata
        self.annual_depreciation_common_equipments = annual_depreciation_common_equipments #共通設備の年間減価償却費[yen/year]
        self.labor_cost_indirect_direct_ratio = labor_cost_indirect_direct_ratio #労務費間接費/直接費比率[-]
        self.annual_maintenance_common_equipment_cost = annual_maintenance_common_equipment_cost #共通設備の年間保守維持費[yen/year]
        self.annual_common_consumables_cost = annual_common_consumables_cost #年間共通消耗品費[yen/year]
      
    def calculate_cost_per_process(self):
        # 1工程あたりの直接労務費[yen/run]
        self.direct_labor_cost_per_process = self.labor_cost_per_hour * self.labor_hours_per_process
        # 1工程あたりの労務費[yen/run]
        self.labor_cost_per_process = self.direct_labor_cost_per_process * (1 + self.labor_cost_indirect_direct_ratio)
        # 前工程に律速される総年間生産数量[pcs/year]
        self.upstream_constrained_annual_production = self.upstream_total_annual_production * self.product_split_count
        # 装置1台の年間生産キャパシティ[pcs/year/unit]
        self.annual_product_capacity_per_unit = self.batch_process_quantity * self.annual_process_capacity_per_unit * self.product_split_count
        # 総年間生産キャパシティ[pcs/year]
        self.total_annual_capacity = self.annual_product_capacity_per_unit * self.num_of_units
        # 装置1台の年間減価償却費[yen/year/unit]
        self.annual_depreciation_per_unit = self.unit_cost / self.depreciation_period

        # 2024/9/5修正
        #総年間生産数量(歩留まり考慮)[pcs/year]
        self.total_annual_production_with_yield = min(self.upstream_constrained_annual_production, self.total_annual_capacity) * self.yield_rate / 100

        # 2024/9/5追加
        # 100mm品総年間生産数量(歩留まり考慮)[pcs/year]
        self.total_annual_production_with_yield_100mm = self.total_annual_production_with_yield * self.production_ratio_100mm / 100

        # 総年間工程実施回数[run/year]
        # self.total_annual_processes = self.total_annual_production_with_yield / self.batch_process_quantity
        self.total_annual_processes = self.total_annual_production_with_yield / self.batch_process_quantity / self.product_split_count

        # 2024/9/5追加
        # 共通設備の年間装置減価償却費配賦後費用[yen/year]
        self.allocated_annual_depreciation = self.annual_depreciation_common_equipments * self.depreciation_allocation_ratio / 100
        # 年間装置減価償却費[yen/year]
        self.annual_depreciation = self.annual_depreciation_per_unit * self.num_of_units + self.allocated_annual_depreciation
        # 年間前工程製品費[yen/year]
        self.annual_upstream_product_cost = self.upstream_total_product_cost * self.upstream_total_annual_production
        # 年間材料費[yen/year]
        self.annual_material_cost = self.material_cost_per_process * self.total_annual_processes
        # 年間労務費[yen/year]
        self.annual_labor_cost = self.labor_cost_per_process * self.total_annual_processes
        # 年間労務時間[h/year]
        self.annual_labor_hours = self.labor_hours_per_process * self.total_annual_processes
        # 年間補助材料費[yen/year]
        self.annual_auxiliary_material_cost = self.auxiliary_material_cost_per_process * self.total_annual_processes
        # 年間水光熱費[yen/year]
        self.annual_utility_cost = self.utility_cost_per_process * self.total_annual_processes
        # 2024/9/5追加
        # 共通設備の年間保守維持費配賦後費用[yen/year]
        self.allocated_annual_maintenance_cost = self.annual_maintenance_common_equipment_cost * self.maintenance_cost_allocation_ratio / 100
        # 年間保守維持費[yen/year]
        self.annual_maintenance_cost = self.maintenance_cost_per_process * self.total_annual_processes + self.allocated_annual_maintenance_cost
        # 年間その他費用[yen/year]
        self.annual_other_cost = self.other_cost_per_process * self.total_annual_processes
        # 2024/9/5追加
        # 年間共通消耗品費配賦後費用[yen/year]
        self.allocated_annual_consumables_cost = self.annual_common_consumables_cost * self.common_consumables_allocation_ratio / 100
        # 年間消耗品費[yen/year]
        self.annual_consumables_cost = self.consumables_cost_per_process * self.total_annual_processes + self.allocated_annual_consumables_cost

        #年間総コスト[yen/year]
        self.total_annual_cost = (
            self.annual_upstream_product_cost +
            self.annual_depreciation + 
            self.annual_material_cost + 
            self.annual_labor_cost + 
            self.annual_auxiliary_material_cost + 
            self.annual_utility_cost + 
            self.annual_maintenance_cost + 
            self.annual_other_cost +
            self.annual_consumables_cost
        )      

        # 前工程の中間製品の総コストを除いた年間総コスト[yen/year]
        self.total_annual_cost_without_upstream_product_cost = (
            self.annual_depreciation + 
            self.annual_material_cost + 
            self.annual_labor_cost + 
            self.annual_auxiliary_material_cost + 
            self.annual_utility_cost + 
            self.annual_maintenance_cost + 
            self.annual_other_cost +
            self.annual_consumables_cost
        )

        # 前工程の中間製品の総コストを除いた年間総コストのうち、100mm相当分[yen/year]
        self.total_annual_cost_without_upstream_product_cost_100mm = (
            self.annual_depreciation + 
            self.annual_material_cost + 
            self.annual_labor_cost + 
            self.annual_auxiliary_material_cost + 
            self.annual_utility_cost + 
            self.annual_maintenance_cost + 
            self.annual_other_cost +
            self.annual_consumables_cost
        ) * self.cost_allocation_ratio_100mm / 100

        # 生産能力利用率[%]
        self.production_capacity_utilization_rate = min(self.upstream_constrained_annual_production, self.total_annual_capacity) / self.total_annual_capacity * 100

        # 中間製品あたりの変動費[yen/pcs] 精度要確認、モンテカルロシミュレーションの下限値と異なる
        self.unit_variable_cost = ((
            self.material_cost_per_process +
            self.labor_cost_per_process +
            self.auxiliary_material_cost_per_process +
            self.utility_cost_per_process + 
            self.other_cost_per_process +
            self.consumables_cost_per_process + 
            self.maintenance_cost_per_process + 
            self.annual_depreciation_per_unit / self.annual_process_capacity_per_unit
        ) / self.batch_process_quantity / self.product_split_count) / (self.yield_rate / 100)

        # 100mm品中間製品あたりの変動費[yen/pcs]
        self.unit_variable_cost_100mm = self.unit_variable_cost * self.cost_allocation_ratio_100mm / 100
        # print('temp_unit_variable_cost',round(self.unit_variable_cost))

        #中間製品あたりの総コスト[yen/pcs]
        self.unit_product_cost = self.total_annual_cost / self.total_annual_production_with_yield
        # print('temp_unit_product_cost',self.unit_product_cost)

        # 100mm品中間製品あたりの総コスト[yen/pcs]
        self.unit_product_cost_100mm = (self.total_annual_cost * self.cost_allocation_ratio_100mm / 100) / self.total_annual_production_with_yield_100mm
    
    def update_parameter_and_calculate_cost(self, parameter_name, new_value):
        setattr(self, parameter_name, new_value)
        self.calculate_cost_per_process()
        return self.unit_product_cost

###################################################################################
# シナリオ別のコスト計算関数
def calculate_total_cost_by_scenario(processes_input, metadata, scenario):
    process_instances = {}
    cost_details_by_process = {}  # 新しい辞書を追加して、各工程のコスト詳細を保存

    # 各工程のインスタンスを作成し、指定されたシナリオに基づくパラメータを使用
    for process_name, scenarios in processes_input.items():
        params = scenarios[scenario]  # シナリオに応じたパラメータを取得
        params.update(metadata)  # メタデータを追加
        process = ProcessCost(**params)
        process_instances[process_name] = process
    
    # 最初の工程のコストを計算
    process_names = list(process_instances.keys())
    process_instances[process_names[0]].calculate_cost_per_process()
    
    # 最初の工程のコスト詳細を保存
    cost_details_by_process[process_names[0]] = {
        # input
        'product_split_count' : process_instances[process_names[0]].product_split_count,
        'batch_process_quantity' : process_instances[process_names[0]].batch_process_quantity,
        'annual_process_capacity_per_unit' : process_instances[process_names[0]].annual_process_capacity_per_unit,
        'num_of_units' : process_instances[process_names[0]].num_of_units,
        'unit_cost' : process_instances[process_names[0]].unit_cost,
        'depreciation_period' : process_instances[process_names[0]].depreciation_period,
        'yield_rate' : process_instances[process_names[0]].yield_rate,
        'material_cost_per_process' : process_instances[process_names[0]].material_cost_per_process,
        'labor_cost_per_hour' : process_instances[process_names[0]].labor_cost_per_hour,
        'labor_hours_per_process' : process_instances[process_names[0]].labor_hours_per_process,
        'auxiliary_material_cost_per_process' : process_instances[process_names[0]].auxiliary_material_cost_per_process,
        'utility_cost_per_process' : process_instances[process_names[0]].utility_cost_per_process,
        'maintenance_cost_per_process' : process_instances[process_names[0]].maintenance_cost_per_process,
        'other_cost_per_process' : process_instances[process_names[0]].other_cost_per_process,
        'production_ratio_100mm' : process_instances[process_names[0]].production_ratio_100mm,
        'cost_allocation_ratio_100mm' : process_instances[process_names[0]].cost_allocation_ratio_100mm,
        'depreciation_allocation_ratio' : process_instances[process_names[0]].depreciation_allocation_ratio,
        'maintenance_cost_allocation_ratio' : process_instances[process_names[0]].maintenance_cost_allocation_ratio,
        'consumables_cost_per_process' : process_instances[process_names[0]].consumables_cost_per_process,
        'common_consumables_allocation_ratio' : process_instances[process_names[0]].common_consumables_allocation_ratio,
        
        # output
        'total_annual_processes': process_instances[process_names[0]].total_annual_processes,
        'upstream_total_product_cost': process_instances[process_names[0]].upstream_total_product_cost,
        'annual_upstream_product_cost': process_instances[process_names[0]].annual_upstream_product_cost,
        # 2024/9/5追加
        'allocated_annual_depreciation': process_instances[process_names[0]].allocated_annual_depreciation,
        'annual_depreciation': process_instances[process_names[0]].annual_depreciation,
        'annual_material_cost': process_instances[process_names[0]].annual_material_cost,
        'annual_labor_cost': process_instances[process_names[0]].annual_labor_cost,
        'annual_labour_hours': process_instances[process_names[0]].annual_labor_hours,
        'annual_auxiliary_material_cost': process_instances[process_names[0]].annual_auxiliary_material_cost,
        'annual_utility_cost': process_instances[process_names[0]].annual_utility_cost,
        # 2024/9/5追加
        'allocated_annual_maintenance_cost': process_instances[process_names[0]].allocated_annual_maintenance_cost,
        'annual_maintenance_cost': process_instances[process_names[0]].annual_maintenance_cost,
        'annual_other_cost': process_instances[process_names[0]].annual_other_cost,
        # 2024/9/5追加
        'allocated_annual_consumables_cost': process_instances[process_names[0]].allocated_annual_consumables_cost,
        'annual_consumables_cost': process_instances[process_names[0]].annual_consumables_cost,
        'production_capacity_utilization_rate' : process_instances[process_names[0]].production_capacity_utilization_rate,
        'upstream_constrained_annual_production' : process_instances[process_names[0]].upstream_constrained_annual_production,
        'total_annual_capacity' : process_instances[process_names[0]].total_annual_capacity,
        'total_annual_production_with_yield' : process_instances[process_names[0]].total_annual_production_with_yield,
        'total_annual_production_with_yield_100mm' : process_instances[process_names[0]].total_annual_production_with_yield_100mm,
        'total_annual_cost' : process_instances[process_names[0]].total_annual_cost,
        'unit_product_cost' : process_instances[process_names[0]].unit_product_cost,
        'unit_product_cost_100mm' : process_instances[process_names[0]].unit_product_cost_100mm,
        # 2024/9/19追加
        'total_annual_cost_without_upstream_product_cost' : process_instances[process_names[0]].total_annual_cost_without_upstream_product_cost,
        'total_annual_cost_without_upstream_product_cost_100mm' : process_instances[process_names[0]].total_annual_cost_without_upstream_product_cost_100mm,
        # 2024/10/1追加
        'unit_variable_cost' : process_instances[process_names[0]].unit_variable_cost,
        'unit_variable_cost_100mm' : process_instances[process_names[0]].unit_variable_cost_100mm,
        # 2024/11/27追加
        'labor_cost_per_process' : process_instances[process_names[0]].labor_cost_per_process,
        'annual_product_capacity_per_unit' : process_instances[process_names[0]].annual_product_capacity_per_unit,
    }

    # 連続した工程のコストを計算し、各工程の出力を次の工程の入力として使用
    for i in range(1, len(process_names)):
        previous_process = process_instances[process_names[i-1]]
        current_process = process_instances[process_names[i]]
        # 前工程の出力を次工程の入力として設定
        current_process.upstream_total_annual_production = previous_process.total_annual_production_with_yield
        current_process.upstream_total_product_cost = previous_process.unit_product_cost
        current_process.calculate_cost_per_process()

        # 各工程のコスト詳細を保存
        cost_details_by_process[process_names[i]] = {
            # input
            'product_split_count' : current_process.product_split_count,
            'batch_process_quantity' : current_process.batch_process_quantity,
            'annual_process_capacity_per_unit' : current_process.annual_process_capacity_per_unit,
            'num_of_units' : current_process.num_of_units,
            'unit_cost' : current_process.unit_cost,
            'depreciation_period' : current_process.depreciation_period,
            'yield_rate' : current_process.yield_rate,
            'material_cost_per_process' : current_process.material_cost_per_process,
            'labor_cost_per_hour' : current_process.labor_cost_per_hour,
            'labor_hours_per_process' : current_process.labor_hours_per_process,
            'auxiliary_material_cost_per_process' : current_process.auxiliary_material_cost_per_process,
            'utility_cost_per_process' : current_process.utility_cost_per_process,
            'maintenance_cost_per_process' : current_process.maintenance_cost_per_process,
            'other_cost_per_process' : current_process.other_cost_per_process,
            'production_ratio_100mm' : current_process.production_ratio_100mm,
            'cost_allocation_ratio_100mm' : current_process.cost_allocation_ratio_100mm,
            'depreciation_allocation_ratio' : current_process.depreciation_allocation_ratio,
            'maintenance_cost_allocation_ratio' : current_process.maintenance_cost_allocation_ratio,
            'consumables_cost_per_process' : current_process.consumables_cost_per_process,
            'common_consumables_allocation_ratio' : current_process.common_consumables_allocation_ratio,

            # output
            'total_annual_processes': current_process.total_annual_processes,
            'upstream_total_product_cost': current_process.upstream_total_product_cost,
            'annual_upstream_product_cost': current_process.annual_upstream_product_cost,
            # 2024/9/5追加
            'allocated_annual_depreciation': current_process.allocated_annual_depreciation,
            'annual_depreciation': current_process.annual_depreciation,
            'annual_material_cost': current_process.annual_material_cost,
            'annual_labor_cost': current_process.annual_labor_cost,
            'annual_labour_hours': current_process.annual_labor_hours,
            'annual_auxiliary_material_cost': current_process.annual_auxiliary_material_cost,
            'annual_utility_cost': current_process.annual_utility_cost,
            # 2024/9/5追加
            'allocated_annual_maintenance_cost': current_process.allocated_annual_maintenance_cost,
            'annual_maintenance_cost': current_process.annual_maintenance_cost,
            'annual_other_cost': current_process.annual_other_cost,
            # 2024/9/5追加
            'allocated_annual_consumables_cost': current_process.allocated_annual_consumables_cost,
            'annual_consumables_cost': current_process.annual_consumables_cost,
            'production_capacity_utilization_rate' : current_process.production_capacity_utilization_rate,
            'upstream_constrained_annual_production' : current_process.upstream_constrained_annual_production,
            'total_annual_capacity' : current_process.total_annual_capacity,
            'total_annual_production_with_yield' : current_process.total_annual_production_with_yield,
            'total_annual_production_with_yield_100mm' : current_process.total_annual_production_with_yield_100mm,
            'total_annual_cost' : current_process.total_annual_cost,
            'unit_product_cost' : current_process.unit_product_cost,
            'unit_product_cost_100mm' : current_process.unit_product_cost_100mm,
            # 2024/9/19追加
            'total_annual_cost_without_upstream_product_cost' : current_process.total_annual_cost_without_upstream_product_cost,
            'total_annual_cost_without_upstream_product_cost_100mm' : current_process.total_annual_cost_without_upstream_product_cost_100mm,
            # 2024/10/1追加
            'unit_variable_cost' : current_process.unit_variable_cost,
            'unit_variable_cost_100mm' : current_process.unit_variable_cost_100mm,
            # 2024/11/27追加
            'labor_cost_per_process' : current_process.labor_cost_per_process,
            'annual_product_capacity_per_unit' : current_process.annual_product_capacity_per_unit,
        }
    
    # 返す値を変更: 最後の工程の単位製品コストと各工程のコスト詳細
    final_process = process_instances[process_names[-1]]
    # final_unit_cost = final_process.unit_product_cost
    final_unit_cost = final_process.unit_product_cost_100mm
    # wafer_production = final_process.total_annual_production_with_yield
    wafer_production = final_process.total_annual_production_with_yield_100mm
    return final_unit_cost,wafer_production, cost_details_by_process

###################################################################################
# 日本語工程名を取得
def prepare_cost_data(costs_by_process, cost_categories):
    labels = list(costs_by_process.keys())
    cost_data = {category: [costs_by_process[process].get(category, 0) for process in labels] 
                 for category in cost_categories}
    return labels, cost_data

###################################################################################
# 年間総コストのプロット関数
def plot_annual_costs_per_process(data_dict, product_choice):
    """
    data_dict: {
       'シナリオ名': {
          '工程名': {
             'annual_depreciation': ...,
             'annual_material_cost': ...,
             'annual_labor_cost': ...,
             ...
          },
          ... # 他の工程
       },
       '別のシナリオ名': {...}
    }
    """

    # 英語キー -> 日本語ラベル の対応表
    cost_category_labels = {
        'annual_depreciation': '減価償却費',
        'annual_material_cost': '材料費',
        'annual_labor_cost': '労務費',
        'annual_auxiliary_material_cost': '補助材料費',
        'annual_utility_cost': '水光熱費',
        'annual_maintenance_cost': '保守維持費',
        'annual_consumables_cost': '消耗品費',
        'annual_other_cost': 'その他費用',
    }

    # コストカテゴリと色の設定
    cost_categories = list(cost_category_labels.keys())
    category_colors = {
        'annual_depreciation': 'blue',
        'annual_material_cost': 'orange',
        'annual_labor_cost': 'green',
        'annual_auxiliary_material_cost': 'red',
        'annual_utility_cost': 'purple',
        'annual_maintenance_cost': 'brown',
        'annual_consumables_cost': 'cyan',
        'annual_other_cost': 'pink',
    }

    # 製品種に応じた工程名辞書を選択
    if product_choice == "基板":
        dict_for_label = tm.jpn_eng_dict_subs_process
    else:
        dict_for_label = tm.jpn_eng_dict_epi_process

    # data_dict は複数シナリオを含むので、シナリオごとに 1つのグラフを描画
    for scenario_name, costs_by_process in data_dict.items():
        # "工程名" の一覧
        processes = list(costs_by_process.keys())

        # 工程名を日本語に変換
        translated_processes = [dict_for_label.get(proc, proc) for proc in processes]

        # Plotly Figure
        fig = go.Figure()

        # 各費目を「横向き積み上げバー」として追加
        for cat in cost_categories:
            cat_values = [costs_by_process[proc].get(cat, 0) for proc in processes]
            # 英語キーから日本語ラベルを取得
            jp_label = cost_category_labels.get(cat, cat)

            fig.add_trace(go.Bar(
                x=cat_values,
                y=translated_processes,
                orientation='h',
                name=jp_label,  # ここを日本語ラベルに
                marker=dict(color=category_colors.get(cat, 'gray')),
                hovertemplate='%{y}<br>%{x} yen<extra></extra>'
            ))

        # レイアウト設定
        fig.update_layout(
            barmode='stack',  # 積み上げ
            title=f"工程ごと費目ごとの年間コスト | {scenario_name}",
            xaxis_title='Annual Cost [yen/year]',
            yaxis_title='工程',
            width=1000,
            height=600
        )

        # グリッド表示など
        fig.update_xaxes(showgrid=True, gridcolor='#ccc')
        fig.update_yaxes(showgrid=True, gridcolor='#eee')

        # Streamlit で表示
        st.plotly_chart(fig, use_container_width=False)


###################################################################################
# 年間製造キャパシティ・稼働率・100mm総年間生産数量のプロット関数
def plot_capacity_per_process(data_dict, product_choice):
    """
    Plot capacities and utilization rates for multiple processes side by side using Plotly.

    data_dict: {
      'シナリオ名': {
         '工程英名': {
            'production_capacity_utilization_rate': float,
            'upstream_constrained_annual_production': float,
            'total_annual_capacity': float,
            'total_annual_production_with_yield_100mm': float,
            ...
         },
         ... # 他の工程
      },
      '別のシナリオ名': {...}
    }

    product_choice: "基板" or "エピ" （工程名を日本語変換するため）
    """

    # 1) 工程の英名一覧を集める
    all_processes = []
    for process_dict in data_dict.values():
        for process_name in process_dict.keys():
            if process_name not in all_processes:
                all_processes.append(process_name)

    # 2) product_choice に応じて辞書を切り替え（基板/エピ）
    if product_choice == "基板":
        dict_for_label = tm.jpn_eng_dict_subs_process
    else:
        dict_for_label = tm.jpn_eng_dict_epi_process

    # 3) 工程名を日本語に変換
    labels = [dict_for_label.get(proc, proc) for proc in all_processes]

    # ---------- グラフ1: 年間製造キャパシティ ----------
    fig1 = go.Figure()
    # シナリオごとに横バーを追加 (barmode='group' で並列)
    for i, (scenario_name, process_dict) in enumerate(data_dict.items()):
        total_annual_capacities = [
            process_dict.get(p, {}).get('total_annual_capacity', 0)
            for p in all_processes
        ]
        fig1.add_trace(go.Bar(
            x=total_annual_capacities,
            y=labels,
            orientation='h',
            name=scenario_name,
            offsetgroup=i  # グループ化
        ))

    fig1.update_layout(
        barmode='group',
        title='装置台数から求まる年間製造キャパシティ[pcs/year]',
        xaxis_title='年間生産数量[pcs/year]',
        yaxis_title='工程',
        width=1000,
        height=600
    )
    fig1.update_xaxes(showgrid=True, gridcolor='#ccc')
    fig1.update_yaxes(showgrid=True, gridcolor='#eee')

    st.plotly_chart(fig1, use_container_width=False)

    # ---------- グラフ2: 稼働率 ----------
    fig2 = go.Figure()
    for i, (scenario_name, process_dict) in enumerate(data_dict.items()):
        utilization_rates = [
            process_dict.get(p, {}).get('production_capacity_utilization_rate', 0)
            for p in all_processes
        ]
        fig2.add_trace(go.Bar(
            x=utilization_rates,
            y=labels,
            orientation='h',
            name=scenario_name,
            offsetgroup=i
        ))

    fig2.update_layout(
        barmode='group',
        title='稼働率[%]',
        xaxis_title='稼働率[%]',
        yaxis_title='工程',
        width=1000,
        height=600
    )
    fig2.update_xaxes(showgrid=True, gridcolor='#ccc')
    fig2.update_yaxes(showgrid=True, gridcolor='#eee')

    st.plotly_chart(fig2, use_container_width=False)

    # ---------- グラフ3: 100mm総年間生産数量(歩留まり考慮) ----------
    fig3 = go.Figure()
    for i, (scenario_name, process_dict) in enumerate(data_dict.items()):
        total_annual_productions_100mm = [
            process_dict.get(p, {}).get('total_annual_production_with_yield_100mm', 0)
            for p in all_processes
        ]
        fig3.add_trace(go.Bar(
            x=total_annual_productions_100mm,
            y=labels,
            orientation='h',
            name=scenario_name,
            offsetgroup=i
        ))

    fig3.update_layout(
        barmode='group',
        title='100mm総年間生産数量(歩留まり考慮)[pcs/year]',
        xaxis_title='100mm総年間生産数量[pcs/year]',
        yaxis_title='工程',
        width=1000,
        height=600
    )
    fig3.update_xaxes(showgrid=True, gridcolor='#ccc')
    fig3.update_yaxes(showgrid=True, gridcolor='#eee')

    st.plotly_chart(fig3, use_container_width=False)

    # ---------- グラフ4: 年間生産数量(歩留まり考慮) ----------
    fig4 = go.Figure()
    for i, (scenario_name, process_dict) in enumerate(data_dict.items()):
        total_annual_productions = [
            process_dict.get(p, {}).get('total_annual_production_with_yield', 0)
            for p in all_processes
        ]
        fig4.add_trace(go.Bar(
            x=total_annual_productions,
            y=labels,
            orientation='h',
            name=scenario_name,
            offsetgroup=i
        ))

    fig4.update_layout(
        barmode='group',
        title='年間生産数量(歩留まり考慮)[pcs/year]',
        xaxis_title='年間生産数量[pcs/year]',
        yaxis_title='工程',
        width=1000,
        height=600
    )
    fig4.update_xaxes(showgrid=True, gridcolor='#ccc')
    fig4.update_yaxes(showgrid=True, gridcolor='#eee')

    st.plotly_chart(fig4, use_container_width=False)

###################################################################################
# 中間製品コスト・中間製品変動費のプロット関数
def plot_unit_product_cost_per_process(data_dict, product_choice):
    """
    data_dict: {
        'シナリオ名': {
            '工程名': {
                'unit_product_cost': <数値>,
                'unit_variable_cost': <数値>,
                ... 
            },
            '別の工程名': {...},
            ...
        },
        '別のシナリオ名': {...}
    }
    product_choice: "基板" または "エピ"
    """

    # 1) すべての工程名を一意に取得（元コードと同様）
    all_processes = []
    for process_dict in data_dict.values():
        for process_name in process_dict.keys():
            if process_name not in all_processes:
                all_processes.append(process_name)

    if product_choice == "基板":
        dict_for_label = tm.jpn_eng_dict_subs_process
    else:
        dict_for_label = tm.jpn_eng_dict_epi_process

    # 3) ラベルを翻訳
    labels = [dict_for_label.get(proc, proc) for proc in all_processes]

    # -----------------------------------------------------------------------
    # まずは「中間製品コスト (unit_product_cost)」のバーを
    # シナリオごとに横向き表示
    # -----------------------------------------------------------------------
    fig_unit = go.Figure()

    for i, (scenario_name, process_dict) in enumerate(data_dict.items()):
        # 各工程のコスト値を取り出す
        unit_product_costs = [
            process_dict.get(proc, {}).get('unit_product_cost', 0) 
            for proc in all_processes
        ]

        # 横向きバー（orientation='h'）で追加
        fig_unit.add_trace(go.Bar(
            x=unit_product_costs,
            y=labels,
            name=scenario_name,
            orientation='h',
            # 小数点なしのカンマ区切りに統一
            text=[f"{cost:,.0f}円" for cost in unit_product_costs],  
            textposition='outside',
            hovertemplate='%{y}<br>%{x:,.0f}円<extra></extra>',
        ))

    fig_unit.update_layout(
        barmode='group',  # 横向きでもグループ化される
        title='各工程の中間製品コスト[製品1個あたり]',
        xaxis_title='Unit Product Cost [yen/pcs]',
        yaxis_title='Process',
        legend_title='Scenario',
        width=1100,
        height=800
    )
    # x 軸に「xxx,xxx」形式を適用
    fig_unit.update_xaxes(tickformat=",.0f")

    st.plotly_chart(fig_unit)

    st.markdown('---')

    # -----------------------------------------------------------------------
    # 続いて「変動費 (unit_variable_cost)」のバーを
    # シナリオごとに横向き表示
    # -----------------------------------------------------------------------
    fig_var = go.Figure()

    for i, (scenario_name, process_dict) in enumerate(data_dict.items()):
        unit_variable_costs = [
            process_dict.get(proc, {}).get('unit_variable_cost', 0)
            for proc in all_processes
        ]

        fig_var.add_trace(go.Bar(
            x=unit_variable_costs,
            y=labels,
            name=scenario_name,
            orientation='h',
            text=[f"{cost:,.0f}円" for cost in unit_variable_costs],
            textposition='outside',
            hovertemplate='%{y}<br>%{x:,.0f}円<extra></extra>',
        ))

    fig_var.update_layout(
        barmode='group',
        title='各工程の中間製品変動費[製品1個あたり] ※労務費減価償却費含む',
        xaxis_title='Unit Variable Cost [yen/pcs]',
        yaxis_title='Process',
        legend_title='Scenario',
        width=1100,
        height=800
    )
    # こちらも x 軸を「xxx,xxx」形式に
    fig_var.update_xaxes(tickformat=",.0f")

    st.plotly_chart(fig_var)

###################################################################################
# シナリオ別の生産数量とウエハー単価のプロット関数
def plot_scenario_scatter(key_results,
                          substrate_point=None,
                          epi_point=None):
    """
    key_results: pd.DataFrame
       - 列名に 'wafer_production', 'wafer_cost', 'senario' が含まれることを想定
         （実際の列名が違う場合は適宜修正してください）

    substrate_point: tuple or None
       - 基板実績 (x, y, label, color) を渡す
       - Noneの場合は描画しない

    epi_point: tuple or None
       - エピ実績 (x, y, label, color) を渡す
       - Noneの場合は描画しない
    """

    # 1) 軸の最大値を計算 (データの最大値を基に少し余裕をもたせる)
    #    key_results 内の wafer_production と wafer_cost の最大値を取得
    x_max_data = key_results['wafer_production'].max()
    y_max_data = key_results['wafer_cost'].max()

    # 実績点も含めたい場合は、substrate_point/epi_point の値も考慮
    # (substrate_point などが None のときはスキップ)
    if substrate_point is not None:
        x_max_data = max(x_max_data, substrate_point[0])
        y_max_data = max(y_max_data, substrate_point[1])
    if epi_point is not None:
        x_max_data = max(x_max_data, epi_point[0])
        y_max_data = max(y_max_data, epi_point[1])

    # 軸の範囲を 0 ～ (最大値 * 1.1) にする
    x_range = [0, x_max_data * 1.1]
    y_range = [0, y_max_data * 1.1]

    # 2) Plotly Figure を生成
    fig = go.Figure()

    # (A) シナリオのデータ点
    fig.add_trace(go.Scatter(
        x=key_results['wafer_production'],
        y=key_results['wafer_cost'],
        mode='markers+text',
        text=key_results['senario'],
        textposition='top center',
        marker=dict(
            symbol='circle',
            size=8,
            color='blue'
        ),
        name='シナリオ'
    ))

    # (B) 基板実績を追加
    if substrate_point is not None:
        sx, sy, s_label, s_color = substrate_point
        fig.add_trace(go.Scatter(
            x=[sx],
            y=[sy],
            mode='markers+text',
            text=[s_label],
            textposition='top center',
            marker=dict(
                symbol='star',
                color=s_color,
                size=14,
                line=dict(width=1, color='black')
            ),
            name='基板実績'
        ))

    # (C) エピ実績を追加
    if epi_point is not None:
        ex, ey, e_label, e_color = epi_point
        fig.add_trace(go.Scatter(
            x=[ex],
            y=[ey],
            mode='markers+text',
            text=[e_label],
            textposition='top center',
            marker=dict(
                symbol='star',
                color=e_color,
                size=14,
                line=dict(width=1, color='black')
            ),
            name='エピ実績'
        ))

    # 3) レイアウト調整
    fig.update_layout(
        title='100mmウエハ単価と100mmウエハ生産数量の関係',
        xaxis_title='100mmウエハ生産数量[pcs/year]',
        yaxis_title='100mmウエハ単価[yen/pcs]',
        showlegend=False,
        width=800,
        height=800
    )

    # 4) 軸レンジを0からに固定 & Y軸をカンマ区切り
    fig.update_xaxes(
        range=x_range,
        showline=True, linecolor='black', gridcolor='#ccc', showgrid=True
    )
    fig.update_yaxes(
        range=y_range,
        showline=True, linecolor='black', gridcolor='#ccc',
        tickformat=",.0f",  # e.g. 123456 -> "123,456"
        showgrid=True
    )

    # 5) Streamlit で表示
    st.plotly_chart(fig)

###################################################################################
# 製品種ごとの工程ごとの生産比率とコスト配賦比率のプロット関数
def plot_product_ratio(data_dict, product_choice):
    """
    各シナリオごとに、工程ごとの production_ratio_100mm と cost_allocation_ratio_100mm を
    分かりやすく表示するグラフを作成します。
    
    Parameters:
    - data_dict: 辞書形式のデータ。構造は以下の通り。
        {
            'シナリオ名1': {
                '工程名A': {
                    'production_ratio_100mm': float,
                    'cost_allocation_ratio_100mm': float,
                    ...
                },
                '工程名B': {...},
                ...
            },
            'シナリオ名2': {...},
            ...
        }
    - product_choice: "基板" または "エピ" （工程名を日本語変換するため）
    """
    
    import plotly.express as px  # カラーパレットのために再インポート
    # 製品種に応じた工程名辞書を選択
    if product_choice == "基板":
        dict_for_label = tm.jpn_eng_dict_subs_process
    else:
        dict_for_label = tm.jpn_eng_dict_epi_process

    # シナリオの一覧を取得
    scenarios = list(data_dict.keys())

    # 全ての工程名を一意に取得（全シナリオを通して）
    all_processes = set()
    for scenario in scenarios:
        all_processes.update(data_dict[scenario].keys())
    all_processes = sorted(all_processes)

    # 工程名を日本語に変換
    translated_processes = [dict_for_label.get(proc, proc) for proc in all_processes]

    # -----------------------
    # グラフ1: 生産比率 100mm (%)
    # -----------------------
    fig_production = go.Figure()

    for scenario in scenarios:
        # 各工程の比率を取得
        production_ratios = [data_dict[scenario].get(proc, {}).get('production_ratio_100mm', 0) for proc in all_processes]

        # 生産比率のバーを追加
        fig_production.add_trace(
            go.Bar(
                x=production_ratios,
                y=translated_processes,
                name=f'{scenario}',
                orientation='h',
                hovertemplate='%{y}<br>生産比率: %{x} %<extra></extra>',
                text=[f"{ratio:.1f}%" for ratio in production_ratios],  # データラベル
                textposition='auto'
            )
        )

    # レイアウトの設定
    fig_production.update_layout(
        title_text='工程ごとの生産比率 100mm (%)',
        barmode='group',  # グループ化
        width=1200,
        height=600,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    # 軸設定
    fig_production.update_xaxes(title_text='比率 (%)', range=[0, 100])
    fig_production.update_yaxes(title_text='工程')

    # グリッド線の設定
    fig_production.update_xaxes(showgrid=True, gridcolor='#ccc')
    fig_production.update_yaxes(showgrid=True, gridcolor='#eee')

    # データラベルのフォントサイズを調整
    fig_production.update_traces(textfont_size=12)

    # Streamlit で表示
    st.plotly_chart(fig_production, use_container_width=True)

    # -----------------------
    # グラフ2: コスト配賦比率 100mm (%)
    # -----------------------
    fig_cost_allocation = go.Figure()

    for scenario in scenarios:
        # 各工程の比率を取得
        cost_allocation_ratios = [data_dict[scenario].get(proc, {}).get('cost_allocation_ratio_100mm', 0) for proc in all_processes]

        # コスト配賦比率のバーを追加
        fig_cost_allocation.add_trace(
            go.Bar(
                x=cost_allocation_ratios,
                y=translated_processes,
                name=f'{scenario}',
                orientation='h',
                hovertemplate='%{y}<br>コスト配賦比率: %{x} %<extra></extra>',
                text=[f"{ratio:.1f}%" for ratio in cost_allocation_ratios],  # データラベル
                textposition='auto'
            )
        )

    # レイアウトの設定
    fig_cost_allocation.update_layout(
        title_text='工程ごとのコスト配賦比率 100mm (%)',
        barmode='group',  # グループ化
        width=1200,
        height=600,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    # 軸設定
    fig_cost_allocation.update_xaxes(title_text='比率 (%)', range=[0, 100])
    fig_cost_allocation.update_yaxes(title_text='工程')

    # グリッド線の設定
    fig_cost_allocation.update_xaxes(showgrid=True, gridcolor='#ccc')
    fig_cost_allocation.update_yaxes(showgrid=True, gridcolor='#eee')

    # データラベルのフォントサイズを調整
    fig_cost_allocation.update_traces(textfont_size=12)

    # Streamlit で表示
    st.plotly_chart(fig_cost_allocation, use_container_width=True)


###################################################################################
# ウエハ1枚あたり費目構成の可視化
def plot_cost_composition_per_wafer(data_dict, product_choice):
    """
    各シナリオについて、
      (各工程の費目年間コスト合計) / (最終的な100mmウエハ年間生産枚数)
    を計算し、その費目内訳を積み上げバーで可視化する。
    """
    # 英語キーから日本語ラベルへの対応辞書を作成
    cost_category_labels = {
        'annual_depreciation': '減価償却費',
        'annual_material_cost': '材料費',
        'annual_labor_cost': '労務費',
        'annual_auxiliary_material_cost': '補助材料費',
        'annual_utility_cost': '水光熱費',
        'annual_maintenance_cost': '保守維持費',
        'annual_consumables_cost': '消耗品費',
        'annual_other_cost': 'その他費用',
    }

    cost_categories = list(cost_category_labels.keys())

    category_colors = {
        'annual_depreciation': 'blue',
        'annual_material_cost': 'orange',
        'annual_labor_cost': 'green',
        'annual_auxiliary_material_cost': 'red',
        'annual_utility_cost': 'purple',
        'annual_maintenance_cost': 'brown',
        'annual_consumables_cost': 'cyan',
        'annual_other_cost': 'pink',
    }

    scenarios = list(data_dict.keys())
    scenario_cost_per_wafer = {s: {} for s in scenarios}

    for scenario in scenarios:
        cost_details = data_dict[scenario]
        processes = list(cost_details.keys())
        last_process = processes[-1]
        wafer_production_100mm = cost_details[last_process].get('total_annual_production_with_yield_100mm', 0)

        category_sums = {cat: 0 for cat in cost_categories}
        for proc_name in processes:
            for cat in cost_categories:
                category_sums[cat] += cost_details[proc_name].get(cat, 0)

        if wafer_production_100mm == 0:
            for cat in cost_categories:
                scenario_cost_per_wafer[scenario][cat] = 0
        else:
            for cat in cost_categories:
                scenario_cost_per_wafer[scenario][cat] = category_sums[cat] / wafer_production_100mm

    fig = go.Figure()

    x_scenarios = scenarios
    for cat in cost_categories:
        y_vals = [scenario_cost_per_wafer[s][cat] for s in x_scenarios]
        # 英語キー -> 日本語ラベルに置き換え
        jp_label = cost_category_labels.get(cat, cat)

        fig.add_trace(go.Bar(
            x=x_scenarios,
            y=y_vals,
            name=jp_label,  # ← ここを日本語ラベルに
            marker=dict(color=category_colors.get(cat, 'gray')),
            hovertemplate='%{x}<br>%{y:,.0f} yen/pcs<extra></extra>'
        ))

    fig.update_layout(
        barmode='stack',
        title='ウエハ1枚あたりの費目別コスト内訳 (100mm品)',
        yaxis_title='ウエハ1枚あたりのコスト [yen/wafer]',
        width=1000,
        height=600
    )
    fig.update_yaxes(tickformat=",.0f", showgrid=True, gridcolor='#ccc')
    st.plotly_chart(fig, use_container_width=False)

################################################################################
# 装置台数のテーブル表示
def show_equipment_units_table(data_dict, product_choice):
    """
    data_dict: {
        "シナリオ名": {
            "工程英名": {
                "num_of_units": <装置台数>,
                ... (その他のキー)
            },
            ...
        },
        ... (別のシナリオ名)
    }

    product_choice: "基板" or "エピ"
    """
    # 製品種に応じた工程名（日本語変換）辞書を選択
    if product_choice == "基板":
        dict_for_label = tm.jpn_eng_dict_subs_process
    else:
        dict_for_label = tm.jpn_eng_dict_epi_process

    # シナリオごとに表示
    for scenario_name, costs_by_process in data_dict.items():
        st.markdown(f"#### {scenario_name} の装置台数")

        rows = []
        for process_name, details in costs_by_process.items():
            # 工程名(英語)を日本語に変換
            jp_process_name = dict_for_label.get(process_name, process_name)
            # 装置台数を取得（なければ 0 とする）し、整数に変換
            # units = int(details.get("num_of_units", 0))
            # 装置台数を取得（なければ 0 とする）する。小数点以下2桁まで表示
            units = details.get("num_of_units", 0)
            rows.append({
                "工程名": jp_process_name,
                "装置台数": units
            })

        # pandas DataFrame 化
        df_units = pd.DataFrame(rows)

        # st.dataframe() の use_container_width=False でコンパクトに表示
        st.dataframe(df_units, use_container_width=False)



###################################################################################
# 入力パラメータ表示
def show_input_parameters(all_process_inputs):
    """
    all_process_inputs: {
       "シナリオ名1": {
           "工程A": {
               "param1": value1,
               "param2": value2,
               ...
           },
           "工程B": {...},
           ...
       },
       "シナリオ名2": {...},
       ...
    }
    """

    for scenario_name, process_input in all_process_inputs.items():
        st.write(f"#### 入力パラメータ (シナリオ: {scenario_name})")

        # 1) 工程の一覧を取得
        processes = list(process_input.keys())

        # 2) 全パラメータ名を集める
        all_params = set()
        for process_name in processes:
            std_params = process_input[process_name].get('standard', {})
            all_params.update(std_params.keys())
        all_params = sorted(all_params)  # ソートしておくと列順が整う

        # 3) DataFrameを (行=工程, 列=パラメータ) で作成
        df = pd.DataFrame(index=processes, columns=all_params)

        # 4) セルを埋める
        for process_name in processes:
            std_params = process_input[process_name].get('standard', {})
            for param_name in all_params:
                df.loc[process_name, param_name] = std_params.get(param_name, None)

        # 5) 工程名を日本語に変換
        # product_choice が関数の引数に含まれていないため、全シナリオに対して基板かエピか分からない
        # ここではシンプルに英語名のまま表示します
        # もしシナリオごとに product_choice が分かるなら、変換も可能
        # 例: 各シナリオに product_choice を追加するなど

        # ここでは例として、すべて基板として変換
        # 実際にはシナリオごとの product_choice を渡す必要があります
        # もしくは、変換をしない場合はそのまま表示

        # 例: 工程名をそのまま使用
        # labels = [tm.jpn_eng_dict_subs_process.get(proc, proc) for proc in processes]
        # df.index = labels

        # そのまま表示
        st.dataframe(df.style.format(precision=2))

###################################################################################
# 出力結果表示
def show_output_results(full_results):
    """
    full_results: {
       "ScenarioA": {
          "工程A": {...},
          "工程B": {...},
          ...
       },
       "ScenarioB": {...}
    }
    """
    st.write("#### 出力（計算結果）一覧")

    for scenario_name, cost_details_by_process in full_results.items():
        st.write(f"### シナリオ: {scenario_name}")

        # cost_details_by_process = {"工程A": {...}, "工程B": {...}, ...}
        # → これを DataFrame に直す
        # orient='index' で 行=工程, 列=パラメータ に変換
        scenario_df = pd.DataFrame.from_dict(cost_details_by_process, orient='index')

        # このままだと列順が無作為になる場合があるので、
        # 適宜 columns=[...] を指定して並べ替えも可

        # 表示
        st.dataframe(scenario_df.style.format(precision=2))

###################################################################################
# パラメータ読み込み
def read_parameters(file_obj):
    """
    file_obj: Streamlit の UploadedFile またはファイルパス(str)
    現在は file_obj.name 等でファイル名が取れる想定
    """

    # もし文字列パスの場合 (古いパス指定) と、 UploadedFile の両対応にする
    # Streamlitのファイルアップロードは 'UploadedFile' オブジェクト
    # pd.ExcelFile は、ファイルパス(str) でも バイナリIO でも読み込める
    xls = pd.ExcelFile(file_obj)

    all_sheet_names = xls.sheet_names

    def process_sheet_data(df):
        df.columns = [col.strip() for col in df.columns]
        process_data = {'standard': {}, 'best': {}, 'worst': {}}
        for _, row in df.iterrows():
            param_name = row['parameters']
            process_data['standard'][param_name] = row['標準']
            process_data['best'][param_name] = row['最良']
            process_data['worst'][param_name] = row['最悪']
        return process_data

    parameters = OrderedDict()
    metadata = {}

    for sheet_name in all_sheet_names:
        if not sheet_name.startswith('_'):
            # skiprows=2, nrows=23 は従来のレイアウト想定のまま
            df = pd.read_excel(xls, sheet_name=sheet_name, skiprows=2, nrows=23)
            processed_data = process_sheet_data(df)
            processed_sheet_name = sheet_name.replace(" ", "_").lower()
            parameters[processed_sheet_name] = processed_data
        elif sheet_name == '__Metadata':
            # df = pd.read_excel(xls, sheet_name=sheet_name, skiprows=2)
            df = pd.read_excel(xls, sheet_name=sheet_name, skiprows=2, nrows=4)
            metadata = df.set_index('parameters')['値'].to_dict()

    return metadata, parameters

###################################################################################
# シミュレーション実行
def run_simulation(file_objs, product_choice):
    """
    file_objs: List of uploaded Excel files
    product_choice: "基板" or "エピ"
    """
    full_results = {}
    full_results_df = {}
    key_results = pd.DataFrame(columns=[
        'senario',
        'wafer_cost',
        'wafer_production',
        'total_annual_cost_without_upstream_product_cost',
        'unit_variable_cost_100mm'
    ])

    all_process_inputs = {}  # 追加: 全シナリオの入力パラメータを保存

    # Logging
    logging.info("start simulation")

    for file_obj in file_objs:
        # ファイル名からシナリオ名を取得
        file_name_no_ext = file_obj.name.rsplit('.', 1)[0]  # 拡張子除去
        scenario_name = file_name_no_ext[25:] if len(file_name_no_ext) > 25 else file_name_no_ext

        # パラメータの読み込み (UploadedFile をそのまま渡す)
        metadata, process_input = read_parameters(file_obj)
        final_cost, wafer_production, cost_details_by_process = calculate_total_cost_by_scenario(
            process_input, metadata, 'standard'
        )

        # 結果を保存
        full_results[scenario_name] = cost_details_by_process
        senario_result_df = pd.DataFrame.from_dict(cost_details_by_process).T
        full_results_df[scenario_name] = senario_result_df

        new_row = pd.DataFrame({
            'senario': [scenario_name],
            'wafer_cost': [final_cost],
            'wafer_production': [wafer_production],
            'total_annual_cost_without_upstream_product_cost': [
                senario_result_df['total_annual_cost_without_upstream_product_cost'].sum()
            ],
            'unit_variable_cost_100mm': [
                senario_result_df['unit_variable_cost_100mm'].sum()
            ]
        })
        key_results = pd.concat([key_results, new_row], ignore_index=True)

        # 追加: 全シナリオの入力パラメータを保存
        all_process_inputs[scenario_name] = process_input

    depr_per_wafer = []
    depr_ratio = []
    for scenario in full_results:
        # 各工程の年間減価償却費を 100mm 品に配賦して合計
        total_depr_100mm = sum(
            details['annual_depreciation'] * details['cost_allocation_ratio_100mm'] / 100
            for details in full_results[scenario].values()
        )
        # 100mm 年間生産枚数
        wafer_prod = key_results.loc[key_results['senario'] == scenario, 'wafer_production'].iat[0]
        # 100mm 単価
        wafer_cost = key_results.loc[key_results['senario'] == scenario, 'wafer_cost'].iat[0]

        # 1枚あたり減価償却費
        p = total_depr_100mm / wafer_prod if wafer_prod > 0 else 0
        depr_per_wafer.append(p)
        # 単価に占める割合(％)
        r = p / wafer_cost * 100 if wafer_cost > 0 else 0
        depr_ratio.append(r)

    # key_results に新しくカラムを追加
    key_results['depr_per_wafer'] = depr_per_wafer
    key_results['depr_ratio']      = depr_ratio

    # ──────────────── 追加ここから ────────────────
    # 各シナリオごとの年間コスト項目を集計
    annual_depr_list     = []
    annual_labor_list    = []
    annual_material_list = []
    annual_other_list    = []
    for scenario, df in full_results_df.items():
        # full_results_df[scenario] は各工程の cost_details を行＝工程列＝コスト項目で持つ DataFrame
        annual_depr_list.append(    df['annual_depreciation'].sum()    )
        annual_labor_list.append(   df['annual_labor_cost'].sum()       )
        annual_material_list.append(df['annual_material_cost'].sum()    )
        # 「その他経費」は補助材料費＋水光熱費＋保守維持費＋消耗品費＋その他費用の合計  
        annual_other_list.append(
            df['annual_auxiliary_material_cost'].sum() +
            df['annual_utility_cost'].sum() +
            df['annual_maintenance_cost'].sum() +
            df['annual_consumables_cost'].sum() +
            df['annual_other_cost'].sum()
        )

    # key_results に新しい列として追加
    key_results['annual_depreciation_total'] = annual_depr_list
    key_results['annual_labor_cost_total']   = annual_labor_list
    key_results['annual_material_cost_total']= annual_material_list
    key_results['annual_other_cost_total']   = annual_other_list


    # summary 用にコピーして列名を日本語化
    formatted_key_results = key_results.copy()
    # formatted_key_results.columns = [
    #     'シナリオ',
    #     '100mmウエハー単価[yen/pcs]',
    #     '100mmウエハー単価中の減価償却費[yen/pcs]',
    #     '100mmウエハー単価中の減価償却費の割合[%]',
    #     '100mm年間生産数量[pcs/year]',
    #     '年間総コスト[yen/year]',
    #     '100mm変動費総額[yen/pcs]'
    # ]
    formatted_key_results.columns = [
        'シナリオ',
        '100mmウエハー単価[yen/pcs]',   
        '100mmウエハー単価中の減価償却費[yen/pcs]',
        '100mmウエハー単価中の減価償却費の割合[%]',
        '100mm年間生産数量[pcs/year]',
        '年間総コスト[yen/year]',
        '100mm変動費総額[yen/pcs]',
        '年間減価償却費[yen/year]',
        '年間労務費[yen/year]',
        '年間材料費[yen/year]',
        '年間その他経費[yen/year]'
    ]

    # 表示フォーマット
    formatted_key_results['100mmウエハー単価[yen/pcs]']              = key_results['wafer_cost'].map(lambda x: f"{x:,.0f}")
    formatted_key_results['100mmウエハー単価中の減価償却費[yen/pcs]']      = key_results['depr_per_wafer'].map(lambda x: f"{x:,.0f}")
    formatted_key_results['100mmウエハー単価中の減価償却費の割合[%]']       = key_results['depr_ratio'].map(lambda x: f"{x:.1f}%")
    formatted_key_results['100mm年間生産数量[pcs/year]']             = key_results['wafer_production'].map(lambda x: f"{round(x):,.0f}")
    formatted_key_results['年間総コスト[yen/year]']                = key_results['total_annual_cost_without_upstream_product_cost'].map(lambda x: f"{x:,.0f}")
    formatted_key_results['100mm変動費総額[yen/pcs]']               = key_results['unit_variable_cost_100mm'].map(lambda x: f"{x:,.0f}")

    # ──────────────── 追加ここから ────────────────
    formatted_key_results['年間減価償却費[yen/year]'] = \
        key_results['annual_depreciation_total'].map(lambda x: f"{x:,.0f}")
    formatted_key_results['年間労務費[yen/year]']   = \
        key_results['annual_labor_cost_total'  ].map(lambda x: f"{x:,.0f}")
    formatted_key_results['年間材料費[yen/year]']  = \
        key_results['annual_material_cost_total'].map(lambda x: f"{x:,.0f}")
    formatted_key_results['年間その他経費[yen/year]']= \
        key_results['annual_other_cost_total'   ].map(lambda x: f"{x:,.0f}")
    # ──────────────── 追加ここまで ────────────────

    # 表示
    st.markdown("---")

    st.markdown('### サマリー')
    st.dataframe(formatted_key_results, hide_index=True)

    st.markdown("---")

    # ------------------------
    # 散布図で「基板 or エピ」の実績点を切り替える
    # ------------------------
    if product_choice == "基板":
        # 基板実績を表示したい場合
        plot_scenario_scatter(
            key_results,
            substrate_point=(573, 197886, "2024年100mm基板実績", "blue"),
            epi_point=None
        )
    else:
        # エピ実績を表示したい場合
        plot_scenario_scatter(
            key_results,
            substrate_point=None,
            epi_point=(223, 359308, "2024年100mmエピ実績", "green")
        )

    st.markdown("---")

    # 工程別コスト可視化
    with st.expander("各工程の中間製品コストと変動費"):
        plot_unit_product_cost_per_process(full_results, product_choice)

    # 年間総コストのプロット
    with st.expander("各工程の費目ごとの年間総コスト"):
        plot_annual_costs_per_process(full_results, product_choice)

    # 年間製造キャパシティ・稼働率・100mm総年間生産数量のプロット
    with st.expander("年間製造キャパシティ・稼働率・100mm総年間生産数量"):
        plot_capacity_per_process(full_results, product_choice)

    # 工程ごとの生産比率とコスト配賦比率の比較
    with st.expander("工程ごとの生産比率とコスト配賦比率"):
        plot_product_ratio(full_results, product_choice)

    with st.expander("ウエハ1枚の費目構成"):
        plot_cost_composition_per_wafer(full_results, product_choice)

    with st.expander("工程ごとの装置台数"):
        show_equipment_units_table(full_results, product_choice)

    # 入力パラメータ表示
    with st.expander("入力パラメータ"):
        show_input_parameters(all_process_inputs)  # 修正: process_input から all_process_inputs に変更

    # 出力結果表示
    with st.expander("計算結果"):
        show_output_results(full_results)

    return full_results_df, key_results

###################################################################################
# メイン関数
def main():
    st.title("NCT wafer cost simulator")
    # st.write("v2.0.1 (2025/1/9) created by Takuya Igarashi")
    # st.write("v2.0.2 (2025/4/14) modified by Takuya Igarashi")
    # st.write("v2.0.3 (2025/4/15) modified by Takuya Igarashi")
    st.write("v2.0.4 (2025/5/8) modified by Takuya Igarashi")

    # アクセスログを一度だけ記録
    if 'access_logged' not in st.session_state:
        logging.info("accessed")
        st.session_state['access_logged'] = True

    # 1) URLパラメータを取得
    query_params = st.query_params
    type_param = query_params.get("type", "基板")

    # 2) セレクトボックスのデフォルト選択を決める
    product_options = ["基板", "エピ"]
    if type_param.lower() == "epi" or type_param == "エピ":
        default_index = 1
    else:
        default_index = 0

    product_choice = st.selectbox(
        "品種を選択してください",
        product_options,
        index=default_index
    )

    # 1) ファイルアップロード
    uploaded_files = st.file_uploader(
        "Excelファイルを選択（複数可）",
        type=["xlsx"],
        accept_multiple_files=True
    )

    # 2) 「計算実行」ボタン
    if uploaded_files:
        if st.button("計算実行"):
            # スピナー表示（処理中ダイアログ）
            with st.spinner("計算中です...しばらくお待ちください。"):
                # 実行
                run_simulation(uploaded_files, product_choice)

    else:
        st.info("Excelファイルをアップロードしてください。")


if __name__ == "__main__":
    main()

    