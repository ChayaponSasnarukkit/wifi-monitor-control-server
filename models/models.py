import enum
from sqlalchemy import UniqueConstraint, Column, Integer, String, Boolean, DateTime, JSON, Enum, ForeignKey
from sqlalchemy.orm import relationship
from models.database import Base

class Scenario(Base):
    __tablename__ = "scenarios"
    scenario_id = Column(Integer, primary_key=True, index=True)
    scenario_name = Column(String, nullable=False, default="")
    scenario_desc = Column(String, nullable=False, default="")
    # if is_using_target_ap==True, then it will required target_ap_ssid, target_ap_password
    # และเปิด server ที่ device นี้โดยอัตโนมัติเมื่อ run_simulation
    is_using_target_ap = Column(Boolean, nullable=False, default=False)
    target_ap_ssid = Column(String, nullable=True)
    target_ap_password = Column(String, nullable=True)
    
    node_configs = relationship("NodeConfiguration", back_populates="scenario")
    simulations = relationship("Simulation", back_populates="scenario")

class Simulation(Base):
    __tablename__ = "simulations"
    id = Column(Integer, primary_key=True, index=True)
    # required
    title = Column(String, nullable=False) # default=id
    data_location = Column(String, nullable=False)
    scenario_snapshot = Column(String, nullable=False) # ป้องกันการเปลี่ยนแปลง scenario ในอนาคตแล้วงง
    state = Column(String, nullable=False, default="running")
    state_message = Column(String, nullable=False, default="")
    created_at = Column(DateTime, nullable=False)
    
    scenario_id = Column(Integer, ForeignKey("scenarios.scenario_id", ondelete="CASCADE"))
    
    scenario = relationship("Scenario", back_populates="simulations")

class NetworkModeEnum(enum.Enum):
    ap = "ap"
    client ="client"

class RadioModeEnum(enum.Enum):
    radio0 = "5G"
    radio1 ="2.4G"

class NodeConfiguration(Base):
    __tablename__ = "node_configs"
    id = Column(Integer, primary_key=True, index=True)
    # required
    control_ip_addr = Column(String, nullable=False)
    alias_name = Column(String, nullable=False)
    network_mode = Column(Enum(NetworkModeEnum), nullable=False)
    network_ssid = Column(String, nullable=False)
    scenario_id = Column(Integer, ForeignKey("scenarios.scenario_id", ondelete="CASCADE"))
    # group all to 1 attribute => simulation_data
    simulation_detail = Column(JSON, nullable=False)
    
    # # only for ap [null if client]
    radio = Column(Enum(RadioModeEnum), nullable=True)
    tx_power = Column(Integer, nullable=True) # have default managed by application
    
    # # only for client [null if ap]
    # simulation_type = Column(String, nullable=True) # validate the request [must have if mode==client]
    # simulation_detail = Column(String, nullable=True) # have default for each type managed by application
    
    # for future use
    is_active = Column(Boolean, nullable=False, default=False)
    
    scenario = relationship("Scenario", back_populates="node_configs")

    __table_args__ = (
        UniqueConstraint('scenario_id', 'control_ip_addr', name='unique_control_ip_constraint'),
    )

    # NOTE 1:
    """
        AP => run simulation as server only [auto]
        client => run simulation as client only [auto]
        
        run as client=> will required simulation_type and timeout [deter, web, file]
                        but other parameters e.g. average_interval_time are optional (have the default one)
        run as server=> no need to config any parameter, it will find what mode client is running and open server automatically with timeout equal to the longest timeout of client in their network
                        [timeout and type of server will not presence in db, but it will be parse at runtime] 
        which mean timeout and type of AP will alway be null
    """
    # NOTE 2: is_active wont be use now