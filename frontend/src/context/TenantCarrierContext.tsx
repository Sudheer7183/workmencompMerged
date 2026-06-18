// /**
//  * TenantCarrierContext — Phase 2 implementation.
//  *
//  * carrierId is now derived from the first carrier returned by
//  * GET /api/v1/tenant/carriers (tenant_carriers in the tenant schema).
//  *
//  * Exposes { carrierId, setCarrierId, availableCarriers } for the future
//  * multi-carrier switcher (Phase 3).
//  *
//  * Phase 1 fallback: when VITE_SKIP_AUTH=true, defaults to carrier_id = 1
//  * (the demo carrier seeded in 0001_initial_schema.py).
//  */

// import React, {
//   createContext,
//   useContext,
//   useState,
//   useEffect,
//   type ReactNode,
// } from "react";
// import axios from "axios";
// import { useAuth } from "@/context/AuthContext";

// export interface TenantCarrier {
//   carrier_id: number;
//   carrier_name: string;
//   carrier_code: string;
// }

// export interface TenantCarrierContextValue {
//   /** Active carrier ID */
//   carrierId: number;
//   /** Phase 3: allow user to switch active carrier from top-bar selector */
//   setCarrierId: (id: number) => void;
//   /** All carriers assigned to this tenant */
//   availableCarriers: TenantCarrier[];
//   /** True while the initial carrier list is loading */
//   isLoadingCarriers: boolean;
// }

// const TenantCarrierContext = createContext<TenantCarrierContextValue | null>(null);

// // Phase 1 / dev bypass default
// const PHASE1_CARRIER_ID = 1;

// async function fetchTenantCarriers(): Promise<TenantCarrier[]> {
//   const { data } = await axios.get<TenantCarrier[]>("/api/v1/tenant/carriers");
//   return data;
// }

// export function TenantCarrierProvider({ children }: { children: ReactNode }): React.JSX.Element {
//   const { isAuthenticated, user } = useAuth();
//   const [carrierId, setCarrierId] = useState<number>(PHASE1_CARRIER_ID);
//   const [availableCarriers, setAvailableCarriers] = useState<TenantCarrier[]>([]);
//   const [isLoadingCarriers, setIsLoadingCarriers] = useState(false);

//   useEffect(() => {
//     // SUPER_ADMIN has no tenant carriers — skip fetch
//     if (!isAuthenticated || !user || user.role === "SUPER_ADMIN") return;

//     setIsLoadingCarriers(true);
//     fetchTenantCarriers()
//       .then((carriers) => {
//         setAvailableCarriers(carriers);
//         if (carriers.length > 0) {
//           // Default to the first carrier in the list
//           setCarrierId(carriers.at(0)?.carrier_id ?? PHASE1_CARRIER_ID);
//         }
//       })
//       .catch((err: unknown) => {
//         console.error("[TenantCarrierContext] carrier fetch error:", err);
//         // Leave carrierId at PHASE1_CARRIER_ID as safe fallback
//       })
//       .finally(() => {
//         setIsLoadingCarriers(false);
//       });
//   }, [isAuthenticated, user]);

//   return (
//     <TenantCarrierContext.Provider
//       value={{ carrierId, setCarrierId, availableCarriers, isLoadingCarriers }}
//     >
//       {children}
//     </TenantCarrierContext.Provider>
//   );
// }

// export function useTenantCarrier(): TenantCarrierContextValue {
//   const ctx = useContext(TenantCarrierContext);
//   if (ctx === null) {
//     throw new Error("useTenantCarrier must be used within TenantCarrierProvider.");
//   }
//   return ctx;
// }

/**
 * TenantCarrierContext — Phase 2 implementation.
 *
 * carrierId is now derived from the first carrier returned by
 * GET /api/v1/tenant/carriers (tenant_carriers in the tenant schema).
 *
 * Exposes { carrierId, setCarrierId, availableCarriers } for the future
 * multi-carrier switcher (Phase 3).
 *
 * Phase 1 fallback: when VITE_SKIP_AUTH=true, defaults to carrier_id = 1
 * (the demo carrier seeded in 0001_initial_schema.py).
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react";
import axios from "axios";
import { useAuth } from "@/context/AuthContext";

export interface TenantCarrier {
  carrier_id: number;
  carrier_name: string;
  carrier_code: string;
}

export interface TenantCarrierContextValue {
  /** Active carrier ID */
  carrierId: number;
  /** Phase 3: allow user to switch active carrier from top-bar selector */
  setCarrierId: (id: number) => void;
  /** All carriers assigned to this tenant */
  availableCarriers: TenantCarrier[];
  /** True while the initial carrier list is loading */
  isLoadingCarriers: boolean;
}

const TenantCarrierContext = createContext<TenantCarrierContextValue | null>(null);

// 0 means "not yet loaded" — all enabled: carrierId > 0 gates suppress requests
// until the real carrier is fetched from the API.
const PHASE1_CARRIER_ID = 0;

async function fetchTenantCarriers(): Promise<TenantCarrier[]> {
  const { data } = await axios.get<TenantCarrier[]>("/api/v1/tenant/carriers");
  return data;
}

export function TenantCarrierProvider({ children }: { children: ReactNode }): React.JSX.Element {
  const { isAuthenticated, user } = useAuth();
  // 0 = not yet loaded; real value set after fetchTenantCarriers() resolves
  const [carrierId, setCarrierId] = useState<number>(0);
  const [availableCarriers, setAvailableCarriers] = useState<TenantCarrier[]>([]);
  const [isLoadingCarriers, setIsLoadingCarriers] = useState(false);

  useEffect(() => {
    // SUPER_ADMIN has no tenant carriers — skip fetch
    if (!isAuthenticated || !user || user.role === "SUPER_ADMIN") return;

    setIsLoadingCarriers(true);
    fetchTenantCarriers()
      .then((carriers) => {
        setAvailableCarriers(carriers);
        if (carriers.length > 0) {
          // Default to the first carrier in the list
          setCarrierId(carriers.at(0)?.carrier_id ?? PHASE1_CARRIER_ID);
        }
      })
      .catch((err: unknown) => {
        console.error("[TenantCarrierContext] carrier fetch error:", err);
        // Leave carrierId at 0 — queries stay disabled until a carrier loads
      })
      .finally(() => {
        setIsLoadingCarriers(false);
      });
  }, [isAuthenticated, user]);

  return (
    <TenantCarrierContext.Provider
      value={{ carrierId, setCarrierId, availableCarriers, isLoadingCarriers }}
    >
      {children}
    </TenantCarrierContext.Provider>
  );
}

export function useTenantCarrier(): TenantCarrierContextValue {
  const ctx = useContext(TenantCarrierContext);
  if (ctx === null) {
    throw new Error("useTenantCarrier must be used within TenantCarrierProvider.");
  }
  return ctx;
}