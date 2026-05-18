"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import {
  scraperApi,
  type ScrapeJobStatus,
  type ScrapeJobStatusValue,
  type ScrapeRunRequest,
  type ScrapeRunResponse,
} from "@/lib/api/endpoints/scraper";

const RUNNING_STATUSES: ScrapeJobStatusValue[] = ["pending", "running"];

const KEYS = {
  all: () => ["scraper"] as const,
  job: (jobId: string) => [...KEYS.all(), "job", jobId] as const,
};

/** Mutation hook to trigger a scrape run. */
export function useScrapeRun() {
  return useMutation<ScrapeRunResponse, Error, ScrapeRunRequest>({
    mutationFn: (req) => scraperApi.run(req),
  });
}

/**
 * Polling hook for scraper job status.
 *
 * - Enabled only when `jobId` is non-null.
 * - Polls every 2 s while status is PENDING or STARTED.
 * - Stops polling once SUCCESS, FAILURE, or REVOKED is reached.
 */
export function useScraperJob(jobId: string | null) {
  return useQuery<ScrapeJobStatus, Error>({
    queryKey: KEYS.job(jobId ?? "__none__"),
    queryFn: () => scraperApi.getJob(jobId!),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status) return 2_000;
      return RUNNING_STATUSES.includes(status) ? 2_000 : false;
    },
    staleTime: 0,
  });
}

export const scraperKeys = KEYS;
