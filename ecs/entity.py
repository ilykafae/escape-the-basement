class EntityManager:
    def __init__(self):
        self.entities = {}
        self.next_id = 0

    def create_entity(self):
        self.next_id += 1
        self.entities[self.next_id] = {}
        return self.next_id
    
    def add_component(self, entity_id, component):
        self.entities[entity_id][type(component)] = component

    def get_entities(self, *qtype):
        for entity_id, components in self.entities.items():
            if all(comp_type in components for comp_type in qtype):
                yield entity_id, components
