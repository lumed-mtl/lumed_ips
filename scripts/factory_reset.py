from lumed_ips.ips_control import IpsLaser

if __name__ == "__main__":
    laser = IpsLaser()
    available_lasers = laser.find_ips_laser()
    
    print("Connected lasers:")
    if available_lasers:
        for i, laser_name in enumerate(available_lasers):
            print(f"\t{i}) ", laser_name)
        selected_laser = int(
            input(
                "\nSelect a laser (default : 0) :",
            )
            or 0
        )
        laser.comport = list(available_lasers)[selected_laser]
    else:
        print("\tNo laser found")
        exit()
        
    print(f"Connecting to laser {laser.comport}")
    laser.connect()
    laser.get_info()
    
    print(f"Returning laser to factory settings - {laser.comport}")
    print(laser.restore_factory_settings())
    
    print(f"disconnecting laser {laser.comport}")
    laser.disconnect()