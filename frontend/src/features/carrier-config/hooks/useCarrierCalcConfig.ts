/**
 * useCarrierCalcConfig — Phase 3.
 *
 * Fetches and caches the carrier calculation engine config.
 * Used by CalcEngineToggle and IngestionProgress to know if the
 * calculation engine is enabled for a given carrier.
 *
 * Reads from GET /api/v1/carrier-calc-config/{carrierId} (REVIEWER+).
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";

export interface CarrierCalcConfig {
  carrier_id: number;
  use_calculation_engine: boolean;
  updated_at: string;
}

interface UpdateCalcConfigBody {
  use_calculation_engine: boolean;
}

const QUERY_KEY = (carrierId: number) => ["carrier-calc-config", carrierId] as const;

async function fetchCalcConfig(carrierId: number): Promise<CarrierCalcConfig> {
  const { data } = await axios.get<CarrierCalcConfig>(
    `/api/v1/carrier-calc-config/${carrierId}`
  );
  return data;
}

async function updateCalcConfig(
  carrierId: number,
  body: UpdateCalcConfigBody
): Promise<CarrierCalcConfig> {
  const { data } = await axios.put<CarrierCalcConfig>(
    `/api/v1/admin/calc-config/${carrierId}`,
    body
  );
  return data;
}

export function useCarrierCalcConfig(carrierId: number) {
  const queryClient = useQueryClient();

  const query = useQuery<CarrierCalcConfig, Error>({
    queryKey: QUERY_KEY(carrierId),
    queryFn: () => fetchCalcConfig(carrierId),
    staleTime: 60_000, // 1 minute — matches Redis TTL cadence
    enabled: carrierId > 0,
  });

  const mutation = useMutation<CarrierCalcConfig, Error, UpdateCalcConfigBody>({
    mutationFn: (body) => updateCalcConfig(carrierId, body),
    onSuccess: (updated) => {
      queryClient.setQueryData(QUERY_KEY(carrierId), updated);
    },
  });

  return {
    config: query.data ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    /** Toggle the engine ON or OFF. Returns the updated config. */
    toggle: (value: boolean) => mutation.mutateAsync({ use_calculation_engine: value }),
    isToggling: mutation.isPending,
  };
}
