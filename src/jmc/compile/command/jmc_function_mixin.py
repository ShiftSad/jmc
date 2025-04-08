from ..datapack_data import Item
from .utils import FormattedText, hash_string_to_string
from ..exception import JMCValueError
from ..tokenizer import Token, TokenType

from .jmc_function import JMCFunction


class ItemMixin(JMCFunction):
    def create_new_item(
            self, item: "Item", modify_nbt: dict[str, Token] | None = None, error_token: Token | None = None) -> "Item":
        """
        Create new item from existing item

        :param item: An Item to copy from
        :param modify_nbt: NBT to modify, defaults to None
        :param error_token: Token to raise an error to, defaults to None
        :return: New Item
        """
        item_type = item.item_type
        nbt = dict(item.raw_nbt)
        if modify_nbt is None:
            modify_nbt = {}
        for key, value_token in modify_nbt.items():
            if key in nbt:
                raise JMCValueError(
                    f"{key} is already inside the nbt",
                    value_token if error_token is None else error_token,
                    self.tokenizer)

            nbt[key] = value_token
        return Item(
            item_type,
            self.datapack.token_dict_to_raw_js_object(nbt, self.tokenizer),
            nbt
        )

    def create_item(self, item_type_param: str = "itemType", display_name_param: str = "displayName",
                    lore_param: str = "lore", nbt_param: str = "nbt", modify_nbt: dict[str, Token] | None = None) -> "Item":
        """
        Create new item from arguments given in the JMCFunction

        :param item_type_param: Paramter to access `self.args`,defaults to "displayName"
        :param display_name_param: Paramter to access `self.args`,defaults to "itemType"
        :param lore_param: Paramter to access `self.args`,defaults to "lore"
        :param nbt_param: Paramter to access `self.args`,defaults to "nbt"
        :param modify_nbt: NBT to modify, defaults to None
        :return: Item
        """
        if modify_nbt is None:
            modify_nbt = {}

        item_type = self.args[item_type_param]
        if item_type.startswith("minecraft:"):
            item_type = item_type[10:]

        lore_json = []
        if self.args[lore_param]:
            lores, _ = self.datapack.parse_list(
                self.raw_args[lore_param].token, self.tokenizer, TokenType.STRING)
            for lore in lores:
                # Format each lore entry as a JSON object
                lore_text = FormattedText(lore, self.raw_args[lore_param].token, self.tokenizer, 
                                   self.datapack, is_default_no_italic=True, is_allow_score_selector=False)
                lore_json.append(str(lore_text))

        nbt = self.tokenizer.parse_js_obj(
            self.raw_args[nbt_param].token) if self.args[nbt_param] else {}

        for key, value_token in modify_nbt.items():
            if key in nbt:
                raise JMCValueError(
                    f"{key} is already inside the nbt",
                    value_token,
                    self.tokenizer)

            nbt[key] = value_token

        bracket_components = []

        if self.args[display_name_param]:
            name_text = self.format_text(
                display_name_param,
                is_default_no_italic=True,
                is_allow_score_selector=False)
            if name_text:
                bracket_components.append(f'custom_name={name_text}')

        if lore_json:
            lore_str = ",".join(lore_json)
            bracket_components.append(f'lore=[{lore_str}]')

        bracket_notation = ""
        if bracket_components:
            bracket_notation = f"[{','.join(bracket_components)}]"

            final_nbt = {}
        if nbt:
            for key, value in nbt.items():
                # Skip custom_name and lore as they're handled separately
                if key not in ["custom_name", "lore"]:
                    final_nbt[key] = value

        return Item(
            f"{item_type}{bracket_notation}",
            self.datapack.token_dict_to_raw_js_object(final_nbt, self.tokenizer),
            final_nbt
        )

class EventMixin(JMCFunction):
    def add_event(self, criteria: str, command: str) -> None:
        """
        Add command that'll run on criteria event

        :param criteria: Minecraft criteria
        :param command: Command to run
        """
        self.add_events(criteria, [command])

    def add_events(self, criteria: str, commands: list[str]) -> None:
        """
        Add multiple commands that'll run on criteria event

        :param criteria: Minecraft criteria
        :param commands: Commands to run
        """
        criteria = criteria.replace("minecraft.", "")
        count = criteria.lower().replace(":", "_")
        if self.is_never_used("on_event", parameters=[criteria]):
            objective = f"on_event_{hash_string_to_string(criteria, 7)}"
            self.datapack.add_objective(
                objective, criteria)
            func_call = self.datapack.add_raw_private_function(
                "on_event", [f"scoreboard players set @s {objective} 0", *commands], count=count)
            self.datapack.add_tick_command(
                f"execute as @a[scores={{{objective}=1..}}] at @s run {func_call}")

        else:
            func = self.datapack.private_functions["on_event"][count]
            func.extend(
                commands
            )
