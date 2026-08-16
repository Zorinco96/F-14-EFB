import pandas as pd
import numpy as np

class EngineInterpolator:
    def __init__(self, csv_path: str):
        self.df = pd.read_csv(csv_path)

    def compute(self, thrust_type: str, altitude_ft: float, mach: float, derate: float = None):
        # Handle DERATE as MIL subcase
        if thrust_type.upper() == "DERATE":
            result = self._interpolate("MIL", altitude_ft, mach)
            if derate:
                scale = derate / 99.0
                result["Thrust_lbf"] *= scale
                result["FuelFlow_pph"] *= scale
                result["RPM_pct"] = derate
            return result

        return self._interpolate(thrust_type.upper(), altitude_ft, mach)

    def _interpolate(self, thrust_type: str, altitude: float, mach: float):
        subset = self.df[self.df["ThrustType"] == thrust_type]
        alts = np.sort(subset["Altitude_ft"].unique())
        machs = np.sort(subset["Mach"].unique())

        # Exact match
        if (altitude in alts) and (mach in machs):
            row = subset[(subset["Altitude_ft"] == altitude) & (subset["Mach"] == mach)].iloc[0]
            return {"Thrust_lbf": row["Thrust_lbf"], "FuelFlow_pph": row["FuelFlow_pph"], "RPM_pct": row["RPM_pct"]}

        alt_low, alt_high = alts[alts <= altitude].max(), alts[alts >= altitude].min()
        mach_low, mach_high = machs[machs <= mach].max(), machs[machs >= mach].min()

        def get_value(alt, mach, col):
            return subset[(subset["Altitude_ft"] == alt) & (subset["Mach"] == mach)][col].values[0]

        results = {}
        for col in ["Thrust_lbf", "FuelFlow_pph"]:
            Q11 = get_value(alt_low, mach_low, col)
            Q12 = get_value(alt_low, mach_high, col)
            Q21 = get_value(alt_high, mach_low, col)
            Q22 = get_value(alt_high, mach_high, col)

            # Interpolate in Mach
            if mach_high == mach_low:
                R1, R2 = Q11, Q21
            else:
                R1 = Q11 + (Q12 - Q11) * (mach - mach_low) / (mach_high - mach_low)
                R2 = Q21 + (Q22 - Q21) * (mach - mach_low) / (mach_high - mach_low)

            # Interpolate in Altitude
            if alt_high == alt_low:
                value = R1
            else:
                value = R1 + (R2 - R1) * (altitude - alt_low) / (alt_high - alt_low)

            results[col] = round(value, 1)

        # Always return RPM of the nearest gridpoint
        results["RPM_pct"] = 99 if thrust_type == "MIL" else 103 if thrust_type == "AB" else 71
        return results
