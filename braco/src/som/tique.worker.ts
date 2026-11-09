/// <reference lib="webworker" />
import { instalarTiquetaque } from './despertador-worker'

instalarTiquetaque(self as unknown as DedicatedWorkerGlobalScope)
