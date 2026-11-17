import { createContext, useContext } from 'react'

// Map<id, modelo> da biblioteca de modelos, disponível para os nós do mapa.
export const ModelosContext = createContext(new Map())
export const useModelos = () => useContext(ModelosContext)
