# PERSIST
event: str = 'Birthday'
names: list[str] = ['jeff', 'lisa', 'a']
# END PERSIST
accept_input: bool = True

print("Name:",names)
while accept_input:
    new_name = input("Add a person:")
    if new_name == "":  
        accept_input = False
    else:
        names.append(new_name)
    print("Name:",names)

