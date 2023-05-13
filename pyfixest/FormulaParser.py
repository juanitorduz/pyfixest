import re

class FixedEffectInteractionError(Exception):
    pass

class CovariateInteractionError(Exception):
    pass

class DuplicateKeyError(Exception):
    pass


class FixestFormulaParser:


    """
    A class for parsing a formula string into its individual components.

    Attributes:
        depvars (list): A list of dependent variables in the formula.
        covars (list): A list of covariates in the formula.
        fevars (list): A list of fixed effect variables in the formula.
        covars_fml (str): A string representation of the covariates in the formula.
        fevars_fml (str): A string representation of the fixed effect variables in the formula.

    Methods:
        __init__(self, fml): Constructor method that initializes the object with a given formula.
        get_fml_dict(self): Returns a dictionary of all fevars & formula without fevars.
        get_var_dict(self): Returns a dictionary of all fevars and list of covars and depvars used in regression with those fevars.

    """

    def __init__(self, fml):

        """
        Constructor method that initializes the object with a given formula.

        Args:
        fml (str): A two-formula string in the form "Y1 + Y2 ~ X1 + X2 | FE1 + FE2".

        Returns:
            None
        """

        #fml =' Y + Y2 ~  i(X1, X2) |csw0(X3, X4)'

        # Clean up the formula string
        fml = "".join(fml.split())

        # Split the formula string into its components
        fml_split = fml.split('|')
        depvars, covars = fml_split[0].split("~")

        if len(fml_split) == 1:
            fevars = "0"
            endogvars = None
            instruments = None
        elif len(fml_split) == 2:
            if "~" in fml_split[1]:
                fevars = "0"
                endogvars, instruments = fml_split[1].split("~")
            else:
                fevars = fml_split[1]
                endogvars = None
                instruments = None
        elif len(fml_split) == 3:
            fevars = fml_split[1]
            endogvars, instruments = fml_split[2].split("~")

        if endogvars is not None:
            if len(endogvars) > len(instruments):
                raise ValueError("The IV system is underdetermined. Only fully determined systems are allowed. Please provide as many instruments as endogenous variables.")
            elif len(endogvars) < len(instruments):
                raise ValueError("The IV system is overdetermined. Only fully determined systems are allowed. Please provide as many instruments as endogenous variables.")
            else:
                pass

        # Parse all individual formula components into lists
        self.depvars = depvars.split("+")
        self.covars = _unpack_fml(covars)
        self.fevars = _unpack_fml(fevars)
        # no fancy syntax for endogvars, instruments allowed
        self.endogvars = endogvars
        self.instruments = instruments

        if instruments is not None:
            self.is_iv = True
            # all rhs variables for the first stage (endog variable replaced with instrument)
            first_stage_covars_list = covars.split("+")
            first_stage_covars_list[first_stage_covars_list.index(endogvars)] = instruments
            self.first_stage_covars_list = "+".join(first_stage_covars_list)
            self.covars_first_stage = _unpack_fml(self.first_stage_covars_list)
            self.depvars_first_stage = endogvars
        else:
            self.is_iv = False
            self.covars_first_stage = None
            self.depvars_first_stage = None

        if self.covars.get("i") is not None:
            self.ivars = dict()
            i_split = self.covars.get("i")[-1].split("=")
            if len(i_split) > 1:
                ref = self.covars.get("i")[-1].split("=")[1]
                ivar_list = self.covars.get("i")[:-1]
                self.covars["i"] = self.covars.get("i")[:-1]
            else:
                ref = None
                ivar_list = self.covars.get("i")

            self.ivars[ref] = ivar_list

        else:
            self.ivars = None


        # Pack the formula components back into strings
        self.covars_fml = _pack_to_fml(self.covars)
        self.fevars_fml = _pack_to_fml(self.fevars)
        if instruments is not None: 
            self.covars_first_stage_fml = _pack_to_fml(self.covars_first_stage)
        else: 
            self.covars_first_stage_fml = None
        #if "^" in self.covars:
        #    raise CovariateInteractionError("Please use 'i()' or ':' syntax to interact covariates.")

        #for  x in ["i", ":"]:
        #    if x in self.fevars:
        #        raise FixedEffectInteractionError("Interacting fixed effects via", x, " is not allowed. Please use '^' to interact fixed effects.")





    def get_fml_dict(self, iv = False):

        """
        Returns a dictionary of all fevars & formula without fevars. The keys are the fixed effect variable combinations.
        The values are lists of formula strings that do not include the fixed effect variables.

        Args:
            iv (bool): If True, the formula dictionary will be returned for the first stage of an IV regression.
                       If False, the formula dictionary will be returned for the second stage of an IV regression / OLS regression.
        Returns:
            dict: A dictionary of the form {"fe1+fe2": ['Y1 ~ X', 'Y2~X'], "fe1+fe3": ['Y1 ~ X', 'Y2~X']} where
            the keys are the fixed effect variable combinations and the values are lists of formula strings
            that do not include the fixed effect variables.
            If IV is True, creates an instance named fml_dict_iv. Otherwise, creates an instance named fml_dict.
        """


        fml_dict = dict()
        for fevar in self.fevars_fml:
            res = []
            for depvar in self.depvars:
                if iv:
                    for covar in self.covars_first_stage_fml:
                        res.append(depvar + '~' + covar)
                else:
                    for covar in self.covars_fml:
                        res.append(depvar + '~' + covar)
            fml_dict[fevar] = res

        if iv:
            self.fml_dict_iv = fml_dict
        else:
            self.fml_dict = fml_dict

    def _transform_fml_dict(self, iv = False):

        fml_dict2 = dict()

        if iv:

            for fe in self.fml_dict_iv.keys():

                fml_dict2[fe] = dict()

                for fml in self.fml_dict_iv.get(fe):
                    depvars, covars = fml.split("~")
                    if fml_dict2[fe].get(depvars) is None:
                        fml_dict2[fe][depvars] = [covars]
                    else:
                        fml_dict2[fe][depvars].append(covars)
        else:

          for fe in self.fml_dict.keys():

              fml_dict2[fe] = dict()

              for fml in self.fml_dict.get(fe):
                  depvars, covars = fml.split("~")
                  if fml_dict2[fe].get(depvars) is None:
                      fml_dict2[fe][depvars] = [covars]
                  else:
                      fml_dict2[fe][depvars].append(covars)

        if iv:
            self.fml_dict2_iv = fml_dict2
        else:
            self.fml_dict2 = fml_dict2



    def get_var_dict(self, iv = False):

        """
        Create a dictionary of all fevars and list of covars and depvars used in regression with those fevars.
        The keys are the fixed effect variable combinations. The values are lists of variables (dependent variables and covariates) of
        the resespective regressions.

        Args:
            iv (bool): If True, the formula dictionary will be returned for the first stage of an IV regression.

        Returns:
            dict: A dictionary of the form {"fe1+fe2": ['Y1', 'X1', 'X2'], "fe1+fe3": ['Y1', 'X1', 'X2']} where
            the keys are the fixed effect variable combinations and the values are lists of variables
            (dependent variables and covariates) used in the regression with those fixed effect variables.

        """
        var_dict = dict()
        if iv:
            for fevar in self.fevars_fml:
                var_dict[fevar] = _flatten_list(self.depvars) + _flatten_list(list(self.covars_first_stage.values()))

        else:
            for fevar in self.fevars_fml:
                var_dict[fevar] = _flatten_list(self.depvars) + _flatten_list(list(self.covars.values()))

        if iv:
            self.var_dict_iv = var_dict
        else:
            self.var_dict = var_dict


def _unpack_fml(x):

    '''
    Given a formula string `x` - e.g. 'X1 + csw(X2, X3)' - , splits it into its constituent variables and their types (if any),
    and returns a dictionary containing the result. The dictionary has the following keys: 'constant', 'sw', 'sw0', 'csw'.
    The values are lists of variables of the respective type.

    Parameters:
    -----------
    x : str
        The formula string to unpack.

    Returns:
    --------
    res_s : dict
        A dictionary containing the unpacked formula. The dictionary has the following keys:
            - 'constant' : list of str
                The list of constant (i.e., non-switched) variables in the formula.
            - 'sw' : list of str
                The list of variables that have a regular switch (i.e., 'sw(var1, var2, ...)' notation) in the formula.
            - 'sw0' : list of str
                The list of variables that have a 'sw0(var1, var2, ..)' switch in the formula.
            - 'csw' : list of str or list of lists of str
                The list of variables that have a 'csw(var1, var2, ..)' switch in the formula.
                Each element in the list can be either a single variable string, or a list of variable strings
                if multiple variables are listed in the switch.
            - 'csw0' : list of str or list of lists of str
                The list of variables that have a 'csw0(var1,var2,...)' switch in the formula.
                Each element in the list can be either a single variable string, or a list of variable strings
                if multiple variables are listed in the switch.

    Raises:
    -------
    ValueError:
        If the switch type is not one of 'sw', 'sw0', 'csw', or 'csw0'.

    Example:
    --------
    >>> _unpack_fml('a+sw(b)+csw(x1,x2)+sw0(d)+csw0(y1,y2,y3)')
    {'constant': ['a'],
     'sw': ['b'],
     'csw': [['x1', 'x2']],
     'sw0': ['d'],
     'csw0': [['y1', 'y2', 'y3']]}
    '''


    # Split the formula into its constituent variables
    var_split = x.split("+")

    res_s = dict()
    res_s['constant'] = []

    for var in var_split:

        # Check if this variable contains a switch
        varlist, sw_type = _find_sw(var)

        # If there's no switch, just add the variable to the list
        if sw_type is None:
            res_s['constant'].append(var)

        # If there's a switch, unpack it and add it to the list
        else:
            if sw_type in ['sw', 'sw0', 'csw', 'csw0', 'i']:
                _check_duplicate_key(res_s, sw_type)
                res_s[sw_type] = varlist
            else:
                raise ValueError("Unsupported switch type")

    # Sort the list by type (strings first, then lists)
    #res_s.sort(key=lambda x: 0 if isinstance(x, str) else 1)

    return res_s




def _pack_to_fml(unpacked):
    """
    Given a dictionary of "unpacked" formula variables, returns a string containing formulas. An "unpacked" formula is a
    deparsed formula that allows for multiple estimations.

    Parameters
    ----------
    unpacked : dict
        A dictionary of unpacked formula variables. The dictionary has the following keys:
            - 'constant' : list of str
                The list of constant (i.e., non-switched) variables in the formula.
            - 'sw' : list of str
                The list of variables that have a regular switch (i.e., 'sw(var1, var2, ...)' notation) in the formula.
            - 'sw0' : list of str
                The list of variables that have a 'sw0(var1, var2, ..)' switch in the formula.
            - 'csw' : list of str or list of lists of str
                The list of variables that have a 'csw(var1, var2, ..)' switch in the formula.
                Each element in the list can be either a single variable string, or a list of variable strings
                if multiple variables are listed in the switch.
            - 'csw0' : list of str or list of lists of str
    """

    res = dict()

    # add up all constant variables
    if 'constant' in unpacked:
         res['constant'] = unpacked['constant']
    else:
        res['constant'] = []

    if 'i' in unpacked:
       if res['constant']:
           res['constant'] =  res['constant'] + [":".join(unpacked['i'])]
       else:
           res['constant'] = [":".join(unpacked['i'])]

    # add up all variable constants (only required for csw)
    if "csw" in unpacked:
        res['variable'] = unpacked['csw']
        variable_type = "csw"
    elif "csw0" in unpacked:
        res['variable'] = unpacked['csw0']
        variable_type = "csw0"
    elif "sw" in unpacked:
        res['variable'] = unpacked['sw']
        variable_type = "sw"
    elif "sw0" in unpacked:
        res['variable'] = unpacked['sw0']
        variable_type = "sw0"
    else:
        res['variable'] = []
        variable_type = None

    if res['constant']:
        const_fml = "+".join(res['constant'])
    else:
        const_fml = []

    variable_fml = []
    if res['variable']:
        if variable_type in ['csw', 'csw0']:
            variable_fml = [ "+".join(res['variable'][:i+1]) for i in range(len(res['variable']))]
        else:
            variable_fml = [res['variable'][i] for i in range(len(res['variable']))]
        if variable_type in ['sw0', 'csw0']:
            variable_fml = ['0'] + variable_fml


    fml_list = []
    if variable_fml:
        if const_fml:
            fml_list = [ const_fml + "+" + variable_fml[i] for i in range(len(variable_fml)) if variable_fml[i] != "0"]
            if variable_type in ['sw0', 'csw0']:
                fml_list = [const_fml] + fml_list
        else:
            fml_list = variable_fml
    else:
        if const_fml:
            fml_list = const_fml
        else:
            raise Exception("Not a valid formula provided.")

    if not isinstance(fml_list, list):
        fml_list = [fml_list]

    return fml_list



def _find_sw(x):
    """
    Search for matches in a string. Matches are either 'sw', 'sw0', 'csw', 'csw0', or 'i'. If a match is found, returns a
    tuple containing a list of the elements found and the type of match. Otherwise, returns the original string and None.

    Args:
        x (str): The string to search for matches in.

    Returns:
        (list[str] or str, str or None): If any matches were found, returns a tuple containing
        a list of the elements found and the type of match (either 'sw', 'sw0', 'csw', or 'csw0').
        Otherwise, returns the original string and None.

    Example:
        _find_sw('sw(var1, var2)') -> (['var1', ' var2'], 'sw')
    """

    # Search for matches in the string
    sw_match = re.findall(r"sw\((.*?)\)", x)
    csw_match = re.findall(r"csw\((.*?)\)", x)
    sw0_match = re.findall(r"sw0\((.*?)\)", x)
    csw0_match = re.findall(r"csw0\((.*?)\)", x)
    i_match = re.findall(r"i\((.*?)\)", x)


    # Check for sw matches
    if sw_match:
        if csw_match:
            return csw_match[0].split(","), "csw"
        else:
            return sw_match[0].split(","), "sw"

    # Check for sw0 matches
    elif sw0_match:
        if csw0_match:
            return csw0_match[0].split(","), "csw0"
        else:
            return sw0_match[0].split(","), "sw0"

    elif i_match:
        return i_match[0].split(","), "i"

    # No matches found
    else:
        return x, None


def _flatten_list(lst):

    """
    Flattens a list that may contain sublists.

    Args:
        lst (list): A list that may contain sublists.

    Returns:
        list: A flattened list with no sublists.

    Examples:
        >>> flatten_list([[1, 2, 3], 4, 5])
        [1, 2, 3, 4, 5]
        >>> flatten_list([1, 2, 3])
        [1, 2, 3]
    """

    flattened_list = []
    for i in lst:
        if isinstance(i, list):
            flattened_list.extend(_flatten_list(i))
        else:
            flattened_list.append(i)
    return flattened_list


def _check_duplicate_key(my_dict, key):

    '''
    Checks if a key already exists in a dictionary. If it does, raises a DuplicateKeyError. Otherwise, does nothing.

    Args:
        my_dict (dict): The dictionary to check for duplicate keys.
        key (str): The key to check for in the dictionary.

    Returns:
        None
    '''

    if key == 'i' and 'i' in my_dict:
        raise DuplicateKeyError("Duplicate key found: " + key + ". Fixed effect syntax i() can only be used once in the input formula.")
    else:
        for key in ['sw', 'csw', 'sw0', 'csw0']:
            if key in my_dict:
                raise DuplicateKeyError("Duplicate key found: " + key + ". Multiple estimation syntax can only be used once on the rhs of the two-sided formula.")
            else:
                None
