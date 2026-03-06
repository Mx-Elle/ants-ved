from random import choice
from board import Entity, neighbors
import numpy as np
import numpy.typing as npt


AntMove = tuple[tuple[int, int], tuple[int, int]]


def valid_neighbors(
    row: int, col: int, walls: npt.NDArray[np.int_]
) -> list[tuple[int, int]]:
    return [n for n in neighbors((row, col), walls.shape) if not walls[n]]


class MyBot:

    def __init__(
        self,
        walls: npt.NDArray[np.int_],
        harvest_radius: int,
        vision_radius: int,
        battle_radius: int,
        max_turns: int,
        time_per_turn: float,
    ) -> None:
        self.walls = walls
        self.collect_radius = harvest_radius
        self.vision_radius = vision_radius
        self.battle_radius = battle_radius
        self.max_turns = max_turns
        self.time_per_turn = time_per_turn

    @property
    def name(self):
        return "ved"


    def wrap_distance(self, p1, p2):
        rows, cols = self.walls.shape
        dr = abs(p1[0] - p2[0])
        dc = abs(p1[1] - p2[1])
        dr = min(dr, rows - dr)
        dc = min(dc, cols - dc)

        return dr + dc


    def detect_clusters(self, ants):
        clusters = []
        visited = set()
        
        for ant in ants:
            if ant in visited:
                continue

            cluster = self.fill_cluster(ant, ants)
            clusters.append(cluster)
            visited.update(cluster)

        return clusters
    

    def fill_cluster(self, starting_ant, ants):
        stack = [starting_ant]
        cluster = set()

        while stack:
            current = stack.pop()
            if current in cluster:
                continue
            cluster.add(current)
            for ant in ants:
                if self.wrap_distance(ant, current) <= self.battle_radius * 2:
                    stack.append(ant)

        return cluster

    def find_largest_cluster(self, clusters):

        if not clusters:
            return set()
        return max(clusters, key=len, default=set())
    
    

    def determine_mode(self, my_cluster, enemy_cluster):
    
        my_size = len(my_cluster)
        enemy_size = len(enemy_cluster)
        if not enemy_cluster:
            return "hill_rush"

        if my_size >= enemy_size * 2 and my_size > 40:
            return "hill_rush"
        
        if my_size >= enemy_size:  
            return "collapse"
        if my_size < enemy_size:
            return "deny"
    
    def determine_roles(self, my_ants, main_cluster, mode):
        roles = {}

        for ant in my_ants:
            if ant in main_cluster:
                roles[ant] = "fighter"

            else:
                if mode == "deny":
                    roles[ant] = "deny_food"
                else:
                    roles[ant] = "harvest"
        return roles
    
    def count_in_radius(self, pos, ants, radius):
        count = 0
        close_ants = []
        for ant in ants:
            if self.wrap_distance(pos, ant) <= radius:
                count += 1
                close_ants.append(ant)
        return count, close_ants

    def move_fighter(self, ant, enemy_ants, my_ants, enemy_hills, mode, valid): 

        best_pos = ant
        best_score = -float('inf')

        friends = [a for a in my_ants if a != ant]
        
        for next_pos in valid:
            score = 0
            friendly_count = self.count_in_radius(next_pos, friends, self.battle_radius)[0] 
            enemy_count = self.count_in_radius(next_pos, enemy_ants, self.battle_radius)[0]

            if friendly_count > enemy_count:
                score += 10 + (friendly_count - enemy_count)
            elif friendly_count == enemy_count:
                score += 1
            else:
                score += -10 - (enemy_count - friendly_count)
            
            if enemy_ants:
                target = min(enemy_ants, key=lambda e: self.wrap_distance(next_pos, e))
                score -= self.wrap_distance(next_pos, target) * 0.5


            if mode == "collapse" and enemy_hills:
                hill = min(enemy_hills, key=lambda h: self.wrap_distance(next_pos, h))
                score -= self.wrap_distance(next_pos, hill) * 0.7

            if mode == "hill_rush":
                nearest_hill = min(enemy_hills, key=lambda h: self.wrap_distance(next_pos, h))
                score -= self.wrap_distance(next_pos, nearest_hill) * 1.0

            if score > best_score:
                best_score = score
                best_pos = next_pos
            

        return best_pos

    def move_harvester(self, ant, food, valid): 
        if not food:
            return choice(valid)
        closest_food = min(food, key=lambda f: self.wrap_distance(f, ant))

        return min(valid, key=lambda n: self.wrap_distance(n, closest_food))
        
    
    def score_food(self, meal, ant, enemy_ants):
        if not enemy_ants:
            return -float('inf')
        
        my_dist = self.wrap_distance(ant, meal)
        enemy_dist = min(self.wrap_distance(enemy, meal) for enemy in enemy_ants)
        difference = my_dist - enemy_dist

        if difference >= -1:
            return difference - 0.1*my_dist
        return -float('inf')
    
    def move_deny(self, ant, my_ants, enemy_ants, food, valid):

        if not food:
            return choice(valid)
        
        best_food = None
        best_score = -float('inf')
        for meal in food: 
            score = self.score_food(meal, ant, enemy_ants)

            if score > best_score:
                best_score = score
                best_food = meal
        if best_food is None:
            return choice(valid)
        

        best_pos = ant
        best_dist = float('inf')

        for next_pos in valid:
            dist = self.wrap_distance(next_pos, best_food)

            friendly_count = self.count_in_radius(next_pos, my_ants, self.battle_radius)[0]
            enemy_count = self.count_in_radius(next_pos, enemy_ants, self.battle_radius)[0]
            if friendly_count < enemy_count:
                continue 

            if dist < best_dist:
                best_dist = dist
                best_pos = next_pos
        return best_pos
            
        

    

    
    def move_ants(
        self,
        vision: set[tuple[tuple[int, int], Entity]],
        stored_food: int,
    ):
        my_ants = {coord for coord, kind in vision if kind == Entity.FRIENDLY_ANT}
        my_hills = {coord for coord, kind in vision if kind == Entity.FRIENDLY_HILL}
        enemy_ants = {coord for coord, kind in vision if kind == Entity.ENEMY_ANT}
        enemy_hills = {coord for coord, kind in vision if kind == Entity.ENEMY_HILL}
        food = {coord for coord, kind in vision if kind == Entity.FOOD}
        
        claimed_destinations = set(my_ants) | my_hills

        my_clusters = self.detect_clusters(my_ants)
        enemy_clusters = self.detect_clusters(enemy_ants)
        main_cluster = self.find_largest_cluster(my_clusters)
        enemy_main_cluster = self.find_largest_cluster(enemy_clusters)
        mode = self.determine_mode(main_cluster, enemy_main_cluster)
        roles = self.determine_roles(my_ants, main_cluster, mode)
        out = set()

        for ant in sorted(my_ants, key=lambda a: roles[a] != "fighter"):
            valid = [v for v in valid_neighbors(*ant, self.walls)
                if v not in claimed_destinations
            ]

            dest = ant 
            if roles[ant] == "fighter" and food:
                if min(self.wrap_distance(ant, f) for f in food) <= 2:
                    roles[ant] = "harvest"

            hill_neighbors = [v for v in valid_neighbors(*ant, self.walls) if v in enemy_hills]
            if hill_neighbors:
                dest = hill_neighbors[0]
            else:
                if valid: 
                    if roles[ant] == "fighter":
                        dest = self.move_fighter(ant, enemy_ants, my_ants, enemy_hills, mode, valid) 
                    elif roles[ant] == "harvest":
                        dest = self.move_harvester(ant, food, valid)
                    else:
                        dest = self.move_deny(ant, my_ants, enemy_ants, food, valid)
                    
                    if dest not in valid:
                        dest = ant
                

            claimed_destinations.remove(ant)
            if dest in claimed_destinations:
                dest = ant
            claimed_destinations.add(dest)
            out.add((ant, dest))            

        return out
